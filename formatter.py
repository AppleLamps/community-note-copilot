from __future__ import annotations

from analyzer import AnalysisResult


def _build_summary(result: AnalysisResult, request_mode: str) -> str:
    if request_mode == "revision":
        return "Updated draft ready"
    verdict = (result.verdict or "Analysis complete").strip()
    return f"Quick take: {verdict}"


def _build_next_prompts(request_mode: str) -> list[str]:
    if request_mode == "revision":
        return [
            "make it even shorter",
            "rewrite it more neutrally",
            "make the note more direct",
        ]
    return [
        "make it shorter",
        "rewrite more neutrally",
        "focus on the strongest source",
    ]


def format_analysis_message(result: AnalysisResult, request_mode: str = "analysis") -> str:
    lines = [
        _build_summary(result, request_mode),
        "",
        "Claim",
        result.claim or "Unavailable",
        "",
        "Verdict",
        result.verdict or "Unavailable",
        "",
        "Recommended form selections",
        f'Is this tweet misleading? {result.form_misleading or "unknown"}',
        f'How is it misleading? {result.form_category or "unknown"}',
        f'Is it potentially harmful? {result.form_harmful or "unknown"}',
        "",
        "Suggested Community Note",
        result.draft_note or "Unavailable",
        "",
        "Sources",
    ]

    if result.sources:
        for index, source in enumerate(result.sources, start=1):
            description = source.get("description") or source.get("url") or "Source"
            url = source.get("url", "")
            lines.append(f"{index}. {description}: {url}")
    else:
        lines.append("No sources returned.")

    lines.extend(["", "Next prompts"])
    for prompt in _build_next_prompts(request_mode):
        lines.append(f'- {prompt}')

    return "\n".join(lines)


def format_parse_failure(raw_text: str) -> str:
    return "\n".join(
        [
            "I couldn't finish the analysis.",
            "Try sending the tweet URL again, paste the claim text directly, or ask for a simpler rewrite.",
            "",
            "Details:",
            raw_text or "No response text returned.",
        ]
    )
