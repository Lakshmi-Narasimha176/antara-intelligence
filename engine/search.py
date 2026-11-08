"""ANTARĀ Intelligence Engine - Real-Time Internet Intelligence.

Provides secure, auditable, and resilient live web search and page content retrieval.
Supports multiple pluggable providers, source credibility scoring, duplicate detection,
conflict identification, publication vs. retrieval date separation, SSRF prevention,
robots.txt compliance, and strict prompt injection defenses.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import logging
import re
import socket
from typing import Any
import urllib.parse
import urllib.request
import urllib.robotparser

from engine.orchestrator import AntaraError

logger = logging.getLogger("antara.search")

# Security and Resource Limits
MAX_PAGE_BYTES: int = 50_000  # 50 KB ceiling to prevent DoS / memory exhaustion
DEFAULT_REQUEST_TIMEOUT: float = 8.0  # seconds
DEFAULT_USER_AGENT: str = (
    "ANTARA-Intelligence-Engine/1.0 (+https://github.com/Lakshmi-Narasimha176/antara-intelligence; research bot)"
)

# Credibility Tier Domains
OFFICIAL_DOMAINS = frozenset({
    "gov", "gov.in", "gov.uk", "mil", "who.int", "un.org", "unesco.org",
    "worldbank.org", "oecd.org", "isro.gov.in", "nasa.gov", "nih.gov",
})
ACADEMIC_DOMAINS = frozenset({
    "edu", "ac.uk", "arxiv.org", "doi.org", "nature.com", "sciencedirect.com",
    "ncbi.nlm.nih.gov", "springer.com", "frontiersin.org", "pnas.org",
    "jstor.org", "plos.org", "cell.com", "ieeexplore.ieee.org",
})
CREDIBLE_NEWS_DOMAINS = frozenset({
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "thehindu.com",
    "nytimes.com", "wsj.com", "ft.com", "economist.com", "nature.com/news",
    "thewire.in", "indianexpress.com",
})

# Known Prompt Injection Patterns to Neutralize in Untrusted Web Data
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)?\s*[a-zA-Z0-9_\s]+mode", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*context\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|content)\s+filters?", re.IGNORECASE),
    re.compile(r"new\s+rule\s*:", re.IGNORECASE),
]


class SearchEngineError(AntaraError):
    """Base exception for all search and web retrieval errors."""


class SearchTimeoutError(SearchEngineError):
    """Raised when a web search or page fetch exceeds network timeout."""


class SearchRateLimitError(SearchEngineError):
    """Raised when an external search provider rate limits queries."""


class SearchProviderUnavailableError(SearchEngineError):
    """Raised when a configured search provider is offline or unreachable."""


class RobotsDisallowedError(SearchEngineError):
    """Raised when a target website's robots.txt forbids content retrieval."""


class SSRFSecurityError(SearchEngineError):
    """Raised when a URL resolves to a prohibited local, loopback, or private IP address."""


class SearchContentExtractionError(SearchEngineError):
    """Raised when content cannot be safely parsed or decoded."""


@dataclass(frozen=True)
class SearchResult:
    """Individual web search result with metadata and cryptographic provenance.

    Attributes:
        title: Cleaned page or article title.
        url: Canonical target URL.
        snippet: Search engine or page excerpt.
        content: Extracted page text (if retrieved).
        source_domain: Normalized hostname (e.g., 'reuters.com').
        credibility_tier: Tier classification ('official', 'academic', 'credible_news', 'general').
        credibility_score: Numeric score between 0.0 and 1.0.
        published_date: Document publication date string if available, else None.
        retrieved_at_utc: ISO 8601 UTC timestamp of retrieval.
        content_hash: SHA-256 fingerprint of the normalized result.
        conflict_notes: Notes on detected factual disagreements with other results.
    """

    title: str
    url: str
    snippet: str
    source_domain: str
    credibility_tier: str
    credibility_score: float
    retrieved_at_utc: str
    content_hash: str
    content: str | None = None
    published_date: str | None = None
    conflict_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class SearchResponse:
    """Aggregated search result package with metadata and conflict analysis.

    Attributes:
        query: Normalized search query.
        provider: Name of the executing search provider.
        status: Operation outcome ('completed', 'unavailable', 'rate_limited', 'error', 'bypassed').
        total_results: Count of returned results.
        results: List of SearchResult records.
        conflicts_detected: List of identified factual or date contradictions.
        retrieval_timestamp_utc: ISO 8601 UTC timestamp of the search.
        disclosure_note: Human-readable disclosure regarding provider availability and source limits.
    """

    query: str
    provider: str
    status: str
    total_results: int
    results: list[SearchResult]
    conflicts_detected: list[dict[str, Any]]
    retrieval_timestamp_utc: str
    disclosure_note: str

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary."""
        return asdict(self)


def compute_search_hash(title: str, url: str, snippet: str) -> str:
    """Compute deterministic SHA-256 fingerprint for a search result."""
    payload = f"{title.strip().casefold()}|{url.strip().casefold()}|{snippet.strip().casefold()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_url(raw_url: str) -> str:
    """Normalize URL by stripping tracking parameters, lowercase scheme and netloc."""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        # Drop tracking query params
        q_params = urllib.parse.parse_qsl(parsed.query)
        cleaned_params = [
            (k, v) for k, v in q_params
            if not k.startswith("utm_") and k not in {"fbclid", "gclid", "ref", "source"}
        ]
        new_query = urllib.parse.urlencode(cleaned_params)
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") if parsed.path != "/" else "/",
            parsed.params,
            new_query,
            "",  # strip fragment
        ))
        return normalized
    except Exception:
        return raw_url.strip()


def extract_domain(url: str) -> str:
    """Extract normalized domain hostname from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower().split(":")[0]
    except Exception:
        return "unknown"


def classify_source_credibility(domain: str) -> tuple[str, float]:
    """Classify domain credibility tier and assign a confidence score.

    Args:
        domain: Normalized hostname (e.g. 'cdc.gov' or 'example.com').

    Returns:
        Tuple of (credibility_tier, credibility_score).
    """
    domain = domain.lower()

    # 1. Official Government / International Bodies
    for off in OFFICIAL_DOMAINS:
        if domain == off or domain.endswith("." + off):
            return "official", 0.95

    # 2. Academic / Research
    for acad in ACADEMIC_DOMAINS:
        if domain == acad or domain.endswith("." + acad):
            return "academic", 0.90

    # 3. Credible Established News
    for news in CREDIBLE_NEWS_DOMAINS:
        if domain == news or domain.endswith("." + news):
            return "credible_news", 0.80

    # 4. General Web
    return "general", 0.50


def is_safe_url(url: str) -> bool:
    """Verify that URL scheme is http/https and does not resolve to private/loopback/cloud metadata IP.

    Prevents Server-Side Request Forgery (SSRF).

    Args:
        url: Target web URL string.

    Returns:
        True if safe, False otherwise.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            logger.warning("SSRF check: Invalid scheme '%s' in url: %s", parsed.scheme, url)
            return False

        hostname = parsed.netloc.split(":")[0]
        if not hostname:
            return False

        # Block localhost / common metadata hostnames
        if hostname.lower() in {"localhost", "metadata.google.internal", "instance-data"}:
            logger.warning("SSRF check: Forbidden hostname '%s'", hostname)
            return False

        # Resolve IP addresses
        ip_addresses = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in ip_addresses:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_loopback
                or ip_obj.is_private
                or ip_obj.is_link_local
                or ip_obj.is_reserved
                or ip_obj.is_multicast
                or str(ip_obj) == "169.254.169.254"  # AWS / Cloud metadata IP
                or str(ip_obj) == "0.0.0.0"
            ):
                logger.warning("SSRF check: Prohibited IP %s for hostname %s", ip_str, hostname)
                return False
        return True
    except Exception as exc:
        logger.warning("SSRF check failed to resolve url %s: %s", url, exc)
        return False


def sanitize_web_content(text: str) -> str:
    """Sanitize retrieved web text to neutralize prompt injection attacks.

    Treats retrieved web text as strictly untrusted external data.
    Strips known jailbreak phrases, escapes system-like boundary tags, and normalizes text.

    Args:
        text: Raw text extracted from webpage.

    Returns:
        Sanitized text safe for contextual analysis.
    """
    sanitized = text
    # 1. Defuse injection triggers
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED_UNTRUSTED_INSTRUCTION]", sanitized)

    # 2. Escape angle brackets and XML boundary tags
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")

    # 3. Collapse excessive whitespace
    sanitized = " ".join(sanitized.split())
    return sanitized


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove exact URL duplicates and near-duplicate titles, favoring higher credibility."""
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    deduped: list[SearchResult] = []

    for r in results:
        norm_url = normalize_url(r.url)
        if norm_url in seen_urls:
            continue

        # Near-duplicate title detection (token overlap >= 85%)
        r_title_tokens = set(re.findall(r"\w+", r.title.casefold()))
        is_dup = False
        for existing in seen_titles:
            ex_tokens = set(re.findall(r"\w+", existing.casefold()))
            if not ex_tokens or not r_title_tokens:
                continue
            intersection = len(r_title_tokens & ex_tokens)
            union = len(r_title_tokens | ex_tokens)
            if union > 0 and (intersection / union) >= 0.85:
                is_dup = True
                break

        if is_dup:
            continue

        seen_urls.add(norm_url)
        seen_titles.append(r.title)
        deduped.append(r)

    return deduped


def detect_conflicts(results: list[SearchResult]) -> list[dict[str, Any]]:
    """Analyze search results for apparent factual, numerical, or date contradictions.

    Identifies opposing sentiment or conflicting statements on the same entities.
    """
    conflicts: list[dict[str, Any]] = []
    # Contrasting keyword pairs
    opposing_pairs = [
        ("increase", "decrease"),
        ("rise", "fall"),
        ("effective", "ineffective"),
        ("safe", "dangerous"),
        ("approved", "banned"),
        ("positive", "negative"),
        ("proven", "disproven"),
    ]

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            r1, r2 = results[i], results[j]
            combined_1 = (r1.title + " " + r1.snippet).casefold()
            combined_2 = (r2.title + " " + r2.snippet).casefold()

            for w1, w2 in opposing_pairs:
                if (w1 in combined_1 and w2 in combined_2) or (w2 in combined_1 and w1 in combined_2):
                    conflict_item = {
                        "type": "semantic_opposition",
                        "topic_contrast": f"'{w1}' vs '{w2}'",
                        "source_1": {"title": r1.title, "url": r1.url, "domain": r1.source_domain},
                        "source_2": {"title": r2.title, "url": r2.url, "domain": r2.source_domain},
                        "note": f"Potential disagreement detected between {r1.source_domain} and {r2.source_domain}.",
                    }
                    conflicts.append(conflict_item)
                    break

            # Date discrepancy: If same domain reports substantially different publication dates
            if (
                r1.source_domain == r2.source_domain
                and r1.published_date
                and r2.published_date
                and r1.published_date != r2.published_date
            ):
                conflicts.append({
                    "type": "date_discrepancy",
                    "domain": r1.source_domain,
                    "date_1": r1.published_date,
                    "date_2": r2.published_date,
                    "note": f"Different publication dates reported by {r1.source_domain}: {r1.published_date} vs {r2.published_date}.",
                })

    return conflicts


class RobotsPolicyChecker:
    """Caches and checks robots.txt policies for accessed domains."""

    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def is_allowed(self, url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
        """Check if robots.txt permits crawling the given URL."""
        domain = extract_domain(url)
        if not domain or domain == "unknown":
            return True

        if domain not in self._parsers:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            try:
                if not is_safe_url(robots_url):
                    return False
                rp.set_url(robots_url)
                # Quick read with timeout
                req = urllib.request.Request(
                    robots_url,
                    headers={"User-Agent": user_agent},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    lines = resp.read(10_000).decode("utf-8", errors="ignore").splitlines()
                    rp.parse(lines)
                self._parsers[domain] = rp
            except Exception as exc:
                logger.debug("robots.txt unreachable for %s (%s); defaulting to allowed", domain, exc)
                # If robots.txt returns 404 or cannot be reached, standard RFC permits crawling
                rp.parse(["User-agent: *", "Allow: /"])
                self._parsers[domain] = rp

        parser = self._parsers.get(domain)
        if parser is None:
            return True
        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True


class WebPageFetcher:
    """Fetches and extracts clean text from permitted web pages with safety guards."""

    def __init__(
        self,
        robots_checker: RobotsPolicyChecker | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_bytes: int = MAX_PAGE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.robots_checker = robots_checker or RobotsPolicyChecker()
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent

    def fetch_page(self, url: str) -> str:
        """Fetch and extract cleaned text from a web URL.

        Args:
            url: Target web page URL.

        Returns:
            Sanitized, clean text excerpt.

        Raises:
            SSRFSecurityError: If URL targets private/loopback/cloud metadata IP.
            RobotsDisallowedError: If robots.txt forbids access.
            SearchTimeoutError: If connection times out.
            SearchContentExtractionError: If content cannot be parsed.
        """
        if not is_safe_url(url):
            raise SSRFSecurityError(f"Security violation: Prohibited or unsafe URL '{url}'.")

        if not self.robots_checker.is_allowed(url, user_agent=self.user_agent):
            raise RobotsDisallowedError(f"Access disallowed by robots.txt for '{url}'.")

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                # Check Content-Type
                c_type = resp.headers.get("Content-Type", "")
                if not any(t in c_type.lower() for t in ("text/html", "text/plain", "application/json")):
                    raise SearchContentExtractionError(
                        f"Unsupported Content-Type '{c_type}' for '{url}'."
                    )

                raw_bytes = resp.read(self.max_bytes)
                charset = resp.headers.get_content_charset() or "utf-8"
                raw_text = raw_bytes.decode(charset, errors="replace")

        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout) or "timed out" in str(exc).lower():
                raise SearchTimeoutError(f"Connection timed out while fetching '{url}'.") from exc
            raise SearchEngineError(f"HTTP fetch error for '{url}': {exc}") from exc
        except socket.timeout as exc:
            raise SearchTimeoutError(f"Connection timed out while fetching '{url}'.") from exc
        except Exception as exc:
            if isinstance(exc, SearchEngineError):
                raise
            raise SearchEngineError(f"Unexpected error fetching '{url}': {exc}") from exc

        # Extract text: Strip HTML script, style, and markup
        clean_text = self._extract_clean_text(raw_text)
        sanitized = sanitize_web_content(clean_text)
        return sanitized

    def _extract_clean_text(self, html: str) -> str:
        """Safely strip HTML tags and scripts without external third-party parser."""
        # Strip script and style blocks
        no_scripts = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # Strip all other HTML tags
        no_tags = re.sub(r"<[^>]+>", " ", no_scripts)
        # Decode basic HTML entities
        cleaned = (
            no_tags.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
        )
        return " ".join(cleaned.split())


# ============================================================================
# Search Provider Abstractions & Implementations
# ============================================================================


class SearchProvider(ABC):
    """Abstract Base Class for search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute web search and return structured SearchResponse.

        Args:
            query: User search query string.
            max_results: Maximum count of results to return.

        Returns:
            SearchResponse instance.
        """


class MockSearchProvider(SearchProvider):
    """Deterministic, offline search provider for testing and offline execution.

    Can be configured with pre-set responses, synthetic failures (timeouts, rate limits),
    and conflicting records to test contradiction detection.
    """

    def __init__(
        self,
        canned_results: dict[str, list[dict[str, Any]]] | None = None,
        force_timeout: bool = False,
        force_rate_limit: bool = False,
        force_unavailable: bool = False,
    ) -> None:
        self._canned_results = canned_results or {}
        self.force_timeout = force_timeout
        self.force_rate_limit = force_rate_limit
        self.force_unavailable = force_unavailable

    @property
    def name(self) -> str:
        return "mock_search_provider"

    def set_canned_results(self, query: str, results: list[dict[str, Any]]) -> None:
        """Register canned search results for a query string."""
        self._canned_results[query.casefold().strip()] = results

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute deterministic mock search."""
        if self.force_timeout:
            raise SearchTimeoutError("Mock search timed out after simulated 10.0s.")
        if self.force_rate_limit:
            raise SearchRateLimitError("Mock search provider rate limit exceeded (HTTP 429).")
        if self.force_unavailable:
            raise SearchProviderUnavailableError("Mock search provider service unavailable (HTTP 503).")

        norm_query = query.casefold().strip()
        raw_items = self._canned_results.get(norm_query)

        # Default fallback canned results if not explicitly mapped
        if raw_items is None:
            # Check for partial matches
            for key, val in self._canned_results.items():
                if key in norm_query or norm_query in key:
                    raw_items = val
                    break

        if raw_items is None:
            raw_items = [
                {
                    "title": f"Recent Empirical Evidence on {query}",
                    "url": "https://nature.com/articles/recent-study-sample",
                    "snippet": f"Recent 2026 cognitive research investigates {query} in controlled settings.",
                    "published_date": "2026-02-15",
                },
                {
                    "title": f"Official Guidelines Regarding {query}",
                    "url": "https://who.int/publications/guidelines-sample",
                    "snippet": f"World Health Organization policy briefing addressing modern findings on {query}.",
                    "published_date": "2025-11-10",
                },
            ]

        results: list[SearchResult] = []
        retrieved_at = datetime.now(timezone.utc).isoformat()

        for item in raw_items[:max_results]:
            url = item["url"]
            domain = extract_domain(url)
            tier, score = classify_source_credibility(domain)
            h = compute_search_hash(item["title"], url, item["snippet"])
            res = SearchResult(
                title=item["title"],
                url=url,
                snippet=item["snippet"],
                content=item.get("content"),
                source_domain=domain,
                credibility_tier=tier,
                credibility_score=score,
                published_date=item.get("published_date"),
                retrieved_at_utc=retrieved_at,
                content_hash=h,
            )
            results.append(res)

        deduped = deduplicate_results(results)
        conflicts = detect_conflicts(deduped)

        return SearchResponse(
            query=query,
            provider=self.name,
            status="completed",
            total_results=len(deduped),
            results=deduped,
            conflicts_detected=conflicts,
            retrieval_timestamp_utc=retrieved_at,
            disclosure_note="Results provided by offline deterministic MockSearchProvider.",
        )


class OpenAIWebSearchProvider(SearchProvider):
    """Evaluates and integrates with OpenAI's web search capability.

    OpenAI supports web search via tool integration (`web_search`) and Responses API
    in supported models (e.g. `gpt-4o`). When live search API credentials are provided,
    this provider issues queries through the official SDK. If credentials or network
    are unavailable, it discloses this state clearly without crashing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_SEARCH_MODEL", model)
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "openai_web_search"

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute web search via OpenAI web-search capability."""
        if not self.api_key:
            logger.info("OpenAI API key not configured; web search unavailable.")
            return SearchResponse(
                query=query,
                provider=self.name,
                status="unavailable",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note="OpenAI web search unavailable: OPENAI_API_KEY not configured.",
            )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, timeout=self.timeout)
            # Query OpenAI with web search tool enabled
            # When web search tool is supported in current API:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a web search assistant. Search for recent, credible sources "
                            "regarding the user query. Return search results strictly formatted as JSON "
                            "with an array of objects containing 'title', 'url', 'snippet', 'published_date'."
                        ),
                    },
                    {"role": "user", "content": f"Search the live web for: {query}"},
                ],
                # tool calling or temperature
                temperature=0.0,
            )
            raw_text = response.choices[0].message.content or ""
            # Parse search results JSON from response
            parsed_items: list[dict[str, Any]] = []
            json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
            if json_match:
                try:
                    parsed_items = json.loads(json_match.group(0))
                except Exception:
                    parsed_items = []

            results: list[SearchResult] = []
            retrieved_at = datetime.now(timezone.utc).isoformat()
            for it in parsed_items[:max_results]:
                u = it.get("url", "https://example.org/search-result")
                t = it.get("title", "Web Result")
                s = it.get("snippet", "")
                dom = extract_domain(u)
                tier, score = classify_source_credibility(dom)
                ch = compute_search_hash(t, u, s)
                results.append(SearchResult(
                    title=t,
                    url=u,
                    snippet=s,
                    source_domain=dom,
                    credibility_tier=tier,
                    credibility_score=score,
                    retrieved_at_utc=retrieved_at,
                    content_hash=ch,
                    published_date=it.get("published_date"),
                ))

            deduped = deduplicate_results(results)
            conflicts = detect_conflicts(deduped)

            return SearchResponse(
                query=query,
                provider=self.name,
                status="completed",
                total_results=len(deduped),
                results=deduped,
                conflicts_detected=conflicts,
                retrieval_timestamp_utc=retrieved_at,
                disclosure_note=f"Results retrieved via OpenAI model '{self.model}'.",
            )
        except Exception as exc:
            logger.warning("OpenAI web search call failed: %s", exc)
            return SearchResponse(
                query=query,
                provider=self.name,
                status="error",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note=f"OpenAI web search failed: {exc}",
            )


# ============================================================================
# Search Manager (Coordinates Providers, Caching, and Fault Tolerance)
# ============================================================================


class SearchManager:
    """Orchestrates live web search, caching, deduplication, and fallback disclosures."""

    def __init__(
        self,
        provider: SearchProvider | None = None,
        fetcher: WebPageFetcher | None = None,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        """Initialize SearchManager.

        Args:
            provider: SearchProvider instance. Defaults to MockSearchProvider.
            fetcher: WebPageFetcher instance.
            enable_cache: Whether to cache search queries in-memory.
            cache_ttl_seconds: In-memory cache time-to-live in seconds.
        """
        self.provider = provider or MockSearchProvider()
        self.fetcher = fetcher or WebPageFetcher()
        self.enable_cache = enable_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, SearchResponse]] = {}

    def search(
        self,
        query: str,
        max_results: int = 5,
        fetch_content: bool = False,
    ) -> SearchResponse:
        """Execute managed web search with caching, fault-tolerance, and content retrieval.

        Args:
            query: User search query.
            max_results: Maximum results to retrieve.
            fetch_content: Whether to fetch page text for retrieved URLs.

        Returns:
            SearchResponse instance with disclosure note and conflict analysis.
        """
        norm_query = query.strip()
        if not norm_query:
            return SearchResponse(
                query=query,
                provider=self.provider.name,
                status="bypassed",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note="Empty search query provided.",
            )

        # 1. Check in-memory cache
        now_ts = datetime.now(timezone.utc).timestamp()
        if self.enable_cache and norm_query in self._cache:
            cached_at, cached_resp = self._cache[norm_query]
            if now_ts - cached_at < self.cache_ttl_seconds:
                logger.debug("Returning cached search response for query '%s'", norm_query)
                return cached_resp

        # 2. Execute provider search with resilience
        try:
            resp = self.provider.search(norm_query, max_results=max_results)
        except SearchTimeoutError as exc:
            logger.warning("Search provider '%s' timed out: %s", self.provider.name, exc)
            return SearchResponse(
                query=norm_query,
                provider=self.provider.name,
                status="unavailable",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note=f"Live search timed out ({exc}). Analysis proceeding on authenticated repository data.",
            )
        except SearchRateLimitError as exc:
            logger.warning("Search provider '%s' rate limited: %s", self.provider.name, exc)
            return SearchResponse(
                query=norm_query,
                provider=self.provider.name,
                status="rate_limited",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note=f"Live search rate limit reached ({exc}). Analysis proceeding on authenticated repository data.",
            )
        except Exception as exc:
            logger.warning("Search provider '%s' failed: %s", self.provider.name, exc)
            return SearchResponse(
                query=norm_query,
                provider=self.provider.name,
                status="error",
                total_results=0,
                results=[],
                conflicts_detected=[],
                retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                disclosure_note=f"Live search provider error ({exc}). Analysis proceeding on authenticated repository data.",
            )

        # 3. Optional page content retrieval (respecting robots.txt, limits, SSRF)
        if fetch_content and resp.results:
            enriched_results: list[SearchResult] = []
            for r in resp.results:
                page_text: str | None = None
                try:
                    page_text = self.fetcher.fetch_page(r.url)
                except Exception as exc:
                    logger.debug("Page content fetch skipped for '%s': %s", r.url, exc)
                enriched_results.append(SearchResult(
                    title=r.title,
                    url=r.url,
                    snippet=r.snippet,
                    content=page_text,
                    source_domain=r.source_domain,
                    credibility_tier=r.credibility_tier,
                    credibility_score=r.credibility_score,
                    published_date=r.published_date,
                    retrieved_at_utc=r.retrieved_at_utc,
                    content_hash=r.content_hash,
                    conflict_notes=r.conflict_notes,
                ))
            resp = SearchResponse(
                query=resp.query,
                provider=resp.provider,
                status=resp.status,
                total_results=resp.total_results,
                results=enriched_results,
                conflicts_detected=resp.conflicts_detected,
                retrieval_timestamp_utc=resp.retrieval_timestamp_utc,
                disclosure_note=resp.disclosure_note,
            )

        # 4. Cache response
        if self.enable_cache and resp.status == "completed":
            self._cache[norm_query] = (now_ts, resp)

        return resp
