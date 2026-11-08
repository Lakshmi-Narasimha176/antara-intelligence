"""ANTARĀ Intelligence Engine - Unified Intelligence Engine (Layer 1).

Orchestrates all Layer 1 subsystems:
- Traditional Knowledge Intelligence (Bhagavad Gītā) & Retrieval Bridge
- Modern Scientific & Empirical Research Intelligence
- Real-Time Live Internet Intelligence & Conflict Detection
- Anti-Hallucination & Fact-Checking Engine
- AI Reasoning Engine with Provider Abstraction (OpenAI / Mock)
- Human-in-the-Loop Governance & Publishing Pipeline
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from engine.fact_checker import FactChecker
from engine.governance import GovernanceEngine, LocalFilePublisher
from engine.knowledge import DEFAULT_DB_PATH, KnowledgeBase
from engine.llm_provider import LLMProvider, MockLLMProvider
from engine.openai_provider import OpenAIProvider
from engine.orchestrator import (
    IntelligenceBrief,
    SubsystemPlan,
    classify_subsystems,
    create_brief,
)
from engine.reasoning import ReasoningAnalysis, ReasoningEngine
from engine.research import ResearchManager
from engine.search import (
    MockSearchProvider,
    OpenAIWebSearchProvider,
    SearchManager,
    SearchProvider,
)
from engine.unified_response import UnifiedResponse, build_unified_response

logger = logging.getLogger("antara.unified_engine")


class UnifiedEngine:
    """ANTARĀ Layer 1 Unified Intelligence Engine.

    Coordinates all core subsystems to deliver end-to-end question processing,
    intelligent subsystem routing, evidence comparison, fact-checking,
    unified response generation, and governance lifecycle management.
    """

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        llm_provider: LLMProvider | None = None,
        search_provider: SearchProvider | None = None,
        fact_checker: FactChecker | None = None,
        governance_engine: GovernanceEngine | None = None,
    ) -> None:
        """Initialize UnifiedEngine.

        Args:
            db_path: Path to shared SQLite database.
            llm_provider: Optional LLMProvider. Defaults to MockLLMProvider if API key missing.
            search_provider: Optional SearchProvider. Defaults to MockSearchProvider.
            fact_checker: Optional FactChecker instance.
            governance_engine: Optional GovernanceEngine instance.
        """
        self.db_path = Path(db_path)
        self.kb = KnowledgeBase(self.db_path)
        self.research_mgr = ResearchManager(self.db_path)

        # Fallback to Mock if OpenAI credentials are not configured
        import os
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if api_key:
                try:
                    self.llm_provider = OpenAIProvider(api_key=api_key)
                except Exception:
                    logger.info("OpenAIProvider initialization failed; using MockLLMProvider.")
                    self.llm_provider = MockLLMProvider()
            else:
                logger.info("OPENAI_API_KEY not configured; using MockLLMProvider.")
                self.llm_provider = MockLLMProvider()

        self.search_provider = search_provider or MockSearchProvider()
        self.search_mgr = SearchManager(provider=self.search_provider)
        self.fact_checker = fact_checker or FactChecker(self.db_path)
        self.reasoning_engine = ReasoningEngine(
            db_path=self.db_path,
            provider=self.llm_provider,
            fact_checker=self.fact_checker,
        )
        self.governance_engine = governance_engine or GovernanceEngine(self.db_path)

    def plan(self, question: str) -> SubsystemPlan:
        """Analyze question and generate intelligent subsystem execution plan.

        Args:
            question: User inquiry string.

        Returns:
            SubsystemPlan instance indicating active subsystems.
        """
        return classify_subsystems(question)

    def process(
        self,
        question: str,
        force_knowledge: bool | None = None,
        force_research: bool | None = None,
        force_web: bool | None = None,
        fetch_web_content: bool = False,
        auto_register_governance: bool = True,
        content_type: str = "philosophical_analysis",
    ) -> tuple[IntelligenceBrief, ReasoningAnalysis, UnifiedResponse]:
        """Execute complete Layer 1 end-to-end intelligence workflow.

        Steps:
        1. Classify question and intelligently select subsystems.
        2. Retrieve verified Gītā knowledge (if indicated).
        3. Retrieve approved empirical research (if indicated).
        4. Query live web intelligence and detect conflicts (if indicated).
        5. Synthesize comparative analysis via ReasoningEngine.
        6. Deterministically audit claims via Module 4 Fact-Checking.
        7. Register output in Module 5 Human Governance pipeline.
        8. Construct 12-dimensional UnifiedResponse.

        Args:
            question: User question string.
            force_knowledge: Override traditional retrieval routing.
            force_research: Override research retrieval routing.
            force_web: Override web retrieval routing.
            fetch_web_content: Whether to fetch page text for web results.
            auto_register_governance: Whether to register the report in Module 5.
            content_type: Governance content category.

        Returns:
            Tuple of (IntelligenceBrief, ReasoningAnalysis, UnifiedResponse).
        """
        # Step 1-4: Intelligent Brief Generation
        brief = create_brief(
            question=question,
            kb=self.kb,
            research_mgr=self.research_mgr,
            search_mgr=self.search_mgr,
            fact_checker=self.fact_checker,
            force_knowledge=force_knowledge,
            force_research=force_research,
            force_web=force_web,
        )

        # Step 5-6: Reasoning Synthesis & Module 4 Fact-Checking Audit
        analysis = self.reasoning_engine.analyze_brief(brief)

        # Step 7: Module 5 Governance Registration
        gov_rec_dict: dict[str, Any] | None = None
        if auto_register_governance:
            gov_rec = self.governance_engine.register_report(
                analysis=analysis,
                content_type=content_type,
                created_by="antara_reasoning_engine_v1",
            )
            gov_rec_dict = gov_rec.to_dict()

        # Step 8: Build 12-Dimensional Unified Response
        unified = build_unified_response(brief, analysis, governance_record=gov_rec_dict)
        return brief, analysis, unified

    def review_report(
        self,
        report_id: str,
        decision: str,
        reviewer: str,
        notes: str,
        locator: str | None = None,
    ) -> Any:
        """Submit a substantive human governance review decision.

        Args:
            report_id: Unique governance report identifier.
            decision: One of 'approved', 'rejected', 'revision_requested'.
            reviewer: Named human reviewer.
            notes: Substantive review rationale (>= 20 characters).
            locator: Optional citation locator.

        Returns:
            Updated GovernanceRecord.
        """
        # Update reasoning engine record if present
        try:
            self.reasoning_engine.record_review(
                report_id=report_id,
                decision=decision,
                reviewer=reviewer,
                notes=notes,
            )
        except Exception as exc:
            logger.debug("Reasoning table review sync skipped: %s", exc)

        action_map = {
            "approved": "approve",
            "approve": "approve",
            "rejected": "reject",
            "reject": "reject",
            "revision_requested": "request_revision",
            "request_revision": "request_revision",
        }
        gov_action = action_map.get(decision.lower(), decision.lower())

        # Update governance engine
        return self.governance_engine.review(
            report_id=report_id,
            action=gov_action,
            reviewer=reviewer,
            notes=notes,
        )

    def authorize_publication(
        self,
        report_id: str,
        authorizer: str,
        channel: str,
        notes: str,
    ) -> Any:
        """Explicitly authorize an approved report for publication."""
        return self.governance_engine.authorize_publication(
            report_id=report_id,
            authorizer=authorizer,
            target_channels=[channel],
            notes=notes,
        )

    def publish_report(
        self,
        report_id: str,
        channel: str = "local_file",
        publisher: Any = None,
    ) -> Any:
        """Publish an authorized report via publishing provider."""
        pub = publisher or LocalFilePublisher()
        self.governance_engine.publish(
            report_id=report_id,
            publisher=pub,
        )
        return self.governance_engine.get_record(report_id)
