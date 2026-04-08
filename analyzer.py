from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from config import Settings, load_settings


SYSTEM_PROMPT = """You are a nonpartisan Community Note analyst. When given a tweet URL or tweet text:
1. Use x_search to fetch the tweet and its thread context when relevant
2. Extract the core factual claim(s) being made
3. Use web_search to find counter-evidence, prioritizing primary sources: government databases (.gov), court filings (PACER, state courts), regulatory filings (SEC EDGAR, FEC, FARA), peer-reviewed research, official statistics, and original datasets. Avoid relying on media articles as primary evidence.
4. Produce your analysis as valid JSON with these fields: claim, verdict, form_misleading (yes/no), form_category (one of: "Factual error", "Missing important context", "Outdated information", "Misleading media or imagery", "Satire or opinion presented as fact"), form_harmful (yes/no), draft_note (under 280 chars, neutral encyclopedic tone, must include at least one source URL), sources (array of {url, description} objects)
5. Return ONLY the JSON object, no markdown fencing, no preamble."""


@dataclass(slots=True)
class AnalysisResult:
    claim: str
    verdict: str
    form_misleading: str
    form_category: str
    form_harmful: str
    draft_note: str
    sources: list[dict[str, str]]
    raw_text: str = ""

    def is_structured(self) -> bool:
        return bool(self.claim or self.verdict or self.draft_note)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "") or ""
    if output_text:
        return output_text

    output = getattr(response, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "output_text":
                return getattr(content, "text", "") or ""
    return ""


def normalize_citations(citations: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for citation in citations:
        if isinstance(citation, dict):
            url = citation.get("url") or citation.get("web_citation", {}).get("url") or citation.get("x_citation", {}).get("url")
            description = citation.get("description") or citation.get("title") or url or ""
        else:
            url = getattr(citation, "url", None)
            if not url and hasattr(citation, "web_citation"):
                url = getattr(citation.web_citation, "url", None)
            if not url and hasattr(citation, "x_citation"):
                url = getattr(citation.x_citation, "url", None)
            description = getattr(citation, "description", None) or getattr(citation, "title", None) or url or ""

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        normalized.append({"url": url, "description": description or url})

    return normalized


def parse_analysis_response(response_text: str, citations: list[Any]) -> AnalysisResult:
    normalized_citations = normalize_citations(citations)

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return AnalysisResult(
            claim="",
            verdict="",
            form_misleading="",
            form_category="",
            form_harmful="",
            draft_note="",
            sources=normalized_citations,
            raw_text=response_text,
        )

    payload_sources = payload.get("sources") or []
    merged_sources = normalize_citations(payload_sources) + [
        source for source in normalized_citations if source["url"] not in {item["url"] for item in normalize_citations(payload_sources)}
    ]

    return AnalysisResult(
        claim=str(payload.get("claim", "")),
        verdict=str(payload.get("verdict", "")),
        form_misleading=str(payload.get("form_misleading", "")),
        form_category=str(payload.get("form_category", "")),
        form_harmful=str(payload.get("form_harmful", "")),
        draft_note=str(payload.get("draft_note", "")),
        sources=merged_sources,
        raw_text=response_text,
    )


class XAIAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _create_client(self) -> Any:
        import httpx
        from openai import OpenAI

        return OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.xai_base_url,
            timeout=httpx.Timeout(120.0),
        )

    async def analyze(self, user_input: str) -> AnalysisResult:
        client = self._create_client()
        response = await asyncio.to_thread(
            client.responses.create,
            model=self.settings.xai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            tools=[
                {"type": "web_search"},
                {"type": "x_search"},
            ],
            include=["no_inline_citations"],
        )
        response_text = extract_output_text(response)
        citations = list(getattr(response, "citations", None) or [])
        return parse_analysis_response(response_text, citations)

    async def revise(self, followup_input: str) -> AnalysisResult:
        return await self.analyze(followup_input)


def build_analyzer(settings: Settings | None = None) -> XAIAnalyzer:
    return XAIAnalyzer(settings or load_settings())
