"""ANTARĀ Intelligence Engine - Governance & Publishing CLI.

Command-line interface to manage report lifecycle states, perform human reviews,
authorize releases, execute cryptographic publishing gates, and inspect audit histories.
"""

import argparse
import logging
from pathlib import Path
import sys

from engine.governance import (
    GovernanceEngine,
    LocalFilePublisher,
)
from engine.knowledge import DEFAULT_DB_PATH

logger = logging.getLogger("antara.governance_cli")


def configure_utf8_output() -> None:
    """Ensure standard output and error streams handle UTF-8 cleanly on Windows."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def run_status(args: argparse.Namespace) -> None:
    """Display governance lifecycle status and fingerprint."""
    engine = GovernanceEngine(args.db_path)
    try:
        rec = engine.get_record(args.report_id)
        print("\n" + "=" * 65)
        print("ANTARĀ GOVERNANCE LIFECYCLE STATUS")
        print(f"Report ID:         {rec.report_id}")
        print(f"Title:             {rec.title}")
        print(f"Content Type:      {rec.content_type}")
        print(f"Current State:     [{rec.current_state.upper()}]")
        print(f"Current Version:   v{rec.current_version}")
        print(f"Content Hash:      {rec.current_hash[:16]}...")
        if rec.approved_by:
            print(f"Approved By:       {rec.approved_by} on {rec.approved_at_utc}")
            print(f"Approved Hash:     {str(rec.approved_hash)[:16]}...")
        if rec.published_at_utc:
            print(f"Published At:      {rec.published_at_utc}")
            print(f"Channels:          {', '.join(rec.publication_channels)}")
        print("=" * 65 + "\n")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_review(args: argparse.Namespace) -> None:
    """Record a human review decision."""
    engine = GovernanceEngine(args.db_path)
    try:
        updated = engine.review(
            report_id=args.report_id,
            action=args.action,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        print(f"\nSuccessfully transitioned report '{updated.report_id}' to [{updated.current_state.upper()}].")
        print(f"Reviewer: {args.reviewer}")
        print(f"Notes:    {args.notes}\n")
    except Exception as exc:
        print(f"Review Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_authorize(args: argparse.Namespace) -> None:
    """Authorize an approved report for publication."""
    engine = GovernanceEngine(args.db_path)
    try:
        channels = [c.strip() for c in args.channel.split(",") if c.strip()]
        updated = engine.authorize_publication(
            report_id=args.report_id,
            authorizer=args.authorizer,
            target_channels=channels,
            notes=args.notes,
        )
        print(f"\nReport '{updated.report_id}' authorized for publication across channels: {channels}")
        print(f"State: [{updated.current_state.upper()}]\n")
    except Exception as exc:
        print(f"Authorization Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_publish(args: argparse.Namespace) -> None:
    """Execute publication through the publisher provider."""
    engine = GovernanceEngine(args.db_path)
    out_dir = Path(args.out_dir) if args.out_dir else Path("outputs/publications")
    publisher = LocalFilePublisher(output_root=out_dir)

    try:
        receipts = engine.publish(
            report_id=args.report_id,
            publisher=publisher,
            publisher_actor=args.actor or "human_publisher",
        )
        print("\n" + "=" * 65)
        print("PUBLICATION RECEIPT")
        for r in receipts:
            print(f"Channel:      {r.channel}")
            print(f"Receipt ID:   {r.receipt_id}")
            print(f"Output Path:  {r.published_uri_or_path}")
            print(f"Fingerprint:  {r.content_hash[:16]}...")
            print(f"Timestamp:    {r.timestamp_utc}")
        print("=" * 65 + "\n")
    except Exception as exc:
        print(f"Publication Gate Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_export(args: argparse.Namespace) -> None:
    """Export report content to JSON or Markdown."""
    engine = GovernanceEngine(args.db_path)
    try:
        rendered = engine.export_report(
            report_id=args.report_id,
            format_type=args.format,
            version=args.version,
        )
        if args.out:
            out_file = Path(args.out)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(rendered, encoding="utf-8")
            print(f"Saved {args.format} export to: {out_file}")
        else:
            print(rendered)
    except Exception as exc:
        print(f"Export Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_audit(args: argparse.Namespace) -> None:
    """Display complete append-only audit trail."""
    engine = GovernanceEngine(args.db_path)
    try:
        entries = engine.get_audit_trail(args.report_id)
        print("\n" + "=" * 72)
        print(f"APPEND-ONLY GOVERNANCE AUDIT TRAIL: {args.report_id}")
        print("-" * 72)
        for e in entries:
            print(f"[{e.timestamp_utc}] {e.from_state} -> {e.to_state} | Action: {e.action} | Actor: {e.actor}")
            print(f"  Hash:  {e.content_hash[:16]}...")
            print(f"  Notes: {e.notes}\n")
        print("=" * 72 + "\n")
    except Exception as exc:
        print(f"Audit Error: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Parse CLI arguments and dispatch commands."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(
        description="ANTARĀ Module 5 Governance CLI - Human-in-the-Loop Lifecycle & Publishing"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Inspect governance lifecycle status")
    p_status.add_argument("--report-id", required=True, help="Report ID to inspect")

    # review
    p_review = subparsers.add_parser("review", help="Record human review decision")
    p_review.add_argument("--report-id", required=True, help="Report ID to review")
    p_review.add_argument("--action", choices=["approve", "reject", "request_revision"], required=True, help="Review decision")
    p_review.add_argument("--reviewer", required=True, help="Reviewer identity and title")
    p_review.add_argument("--notes", required=True, help="Substantive review notes (>= 15 characters)")

    # authorize
    p_auth = subparsers.add_parser("authorize", help="Authorize an approved report for publication")
    p_auth.add_argument("--report-id", required=True, help="Report ID to authorize")
    p_auth.add_argument("--authorizer", required=True, help="Authorizing human name/title")
    p_auth.add_argument("--channel", default="local_file", help="Comma-separated channels (e.g. local_file,website)")
    p_auth.add_argument("--notes", default="Publication authorization confirmed by editorial board.", help="Authorization notes")

    # publish
    p_pub = subparsers.add_parser("publish", help="Publish authorized report across configured channels")
    p_pub.add_argument("--report-id", required=True, help="Report ID to publish")
    p_pub.add_argument("--out-dir", help="Output directory for published artifacts")
    p_pub.add_argument("--actor", help="Publishing operator name")

    # export
    p_exp = subparsers.add_parser("export", help="Export report to JSON or Markdown")
    p_exp.add_argument("--report-id", required=True, help="Report ID to export")
    p_exp.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Export format")
    p_exp.add_argument("--version", type=int, help="Optional version number (defaults to latest)")
    p_exp.add_argument("--out", "-o", help="Optional output file path")

    # audit
    p_audit = subparsers.add_parser("audit", help="Inspect append-only audit trail")
    p_audit.add_argument("--report-id", required=True, help="Report ID to inspect")

    args = parser.parse_args()

    if args.command == "status":
        run_status(args)
    elif args.command == "review":
        run_review(args)
    elif args.command == "authorize":
        run_authorize(args)
    elif args.command == "publish":
        run_publish(args)
    elif args.command == "export":
        run_export(args)
    elif args.command == "audit":
        run_audit(args)


if __name__ == "__main__":
    main()
