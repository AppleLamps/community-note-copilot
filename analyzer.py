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
4. Produce your analysis with these fields: claim, verdict, form_misleading (yes/no), form_category (one of: "Factual error", "Missing important context", "Outdated information", "Misleading media or imagery", "Satire or opinion presented as fact"), form_harmful (yes/no), draft_note (under 280 chars, neutral encyclopedic tone, must include at least one source URL), sources (array of {url, description} objects)."""


REVISION_SYSTEM_PROMPT = """You are revising an existing Community Note draft. Rewrite the draft according to the user's instructions while:
- Keeping the same factual claim and verdict unless explicitly told otherwise
- Preserving sources from the prior draft (do not invent new ones)
- Maintaining a nonpartisan, encyclopedic tone
- Keeping the draft_note under 280 characters and including at least one source URL
- Changing only what the user asked

Do not perform any new web searches. Use only the evidence supplied."""


ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "claim",
        "verdict",
        "form_misleading",
        "form_category",
        "form_harmful",
        "draft_note",
        "sources",
    ],
    "properties": {
        "claim": {"type": "string"},
        "verdict": {"type": "string"},
        "form_misleading": {"type": "string", "enum": ["yes", "no"]},
        "form_category": {
            "type": "string",
            "enum": [
                "Factual error",
                "Missing important context",
                "Outdated information",
                "Misleading media or imagery",
                "Satire or opinion presented as fact",
            ],
        },
        "form_harmful": {"type": "string", "enum": ["yes", "no"]},
        "draft_note": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url", "description"],
                "properties": {
                    "url": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
}


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
        return bool(self.claim and self.draft_note)

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
    payload_normalized = normalize_citations(payload_sources)
    payload_urls = {item["url"] for item in payload_normalized}
    merged_sources = payload_normalized + [
        source for source in normalized_citations if source["url"] not in payload_urls
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


def build_revision_input(prior: AnalysisResult, followup_text: str, original_user_input: str = "") -> str:
    source_lines = "\n".join(f'- {item.get("url", "")}: {item.get("description", "")}' for item in prior.sources) or "- none"
    return (
        "Revise the previously drafted Community Note.\n\n"
        f"Original user input:\n{original_user_input}\n\n"
        f"Claim:\n{prior.claim}\n\n"
        f"Verdict:\n{prior.verdict}\n\n"
        f"Current draft note:\n{prior.draft_note}\n\n"
        f"Current category:\n{prior.form_category}\n\n"
        f"Sources:\n{source_lines}\n\n"
        f"User follow-up request:\n{followup_text}"
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
            text={
                "format": {
                    "type": "json_schema",
                    "name": "community_note_analysis",
                    "schema": ANALYSIS_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )
        response_text = extract_output_text(response)
        citations = list(getattr(response, "citations", None) or [])
        return parse_analysis_response(response_text, citations)

    async def revise(
        self,
        prior: AnalysisResult,
        followup_text: str,
        original_user_input: str = "",
    ) -> AnalysisResult:
        client = self._create_client()
        revision_input = build_revision_input(prior, followup_text, original_user_input)
        response = await asyncio.to_thread(
            client.responses.create,
            model=self.settings.xai_model,
            input=[
                {"role": "system", "content": REVISION_SYSTEM_PROMPT},
                {"role": "user", "content": revision_input},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "community_note_analysis",
                    "schema": ANALYSIS_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )
        response_text = extract_output_text(response)
        citations = list(getattr(response, "citations", None) or [])
        result = parse_analysis_response(response_text, citations)
        # Preserve prior sources if model omitted them.
        if not result.sources:
            result.sources = list(prior.sources)
        return result


def build_analyzer(settings: Settings | None = None) -> XAIAnalyzer:
    return XAIAnalyzer(settings or load_settings())
