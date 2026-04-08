from __future__ import annotations

import re

from analyzer import AnalysisResult


MARKDOWN_V2_SPECIALS = "\\_*[]()~`>#+-=|{}.!"
URL_PATTERN = re.compile(r"https?://\S+")


def escape_markdown_v2(text: str) -> str:
    escaped = text
    for char in MARKDOWN_V2_SPECIALS:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def escape_markdown_preserving_urls(text: str) -> str:
    parts: list[str] = []
    last_index = 0
    for match in URL_PATTERN.finditer(text):
        parts.append(escape_markdown_v2(text[last_index:match.start()]))
        parts.append(match.group(0))
        last_index = match.end()
    parts.append(escape_markdown_v2(text[last_index:]))
    return "".join(parts)


def format_analysis_message(result: AnalysisResult) -> str:
    lines = [
        "*Claim identified*",
        escape_markdown_v2(result.claim or "Unavailable"),
        "",
        "*Verdict*",
        escape_markdown_v2(result.verdict or "Unavailable"),
        "",
        "*CN Form Selections*",
        escape_markdown_v2(f'Is this tweet misleading? {result.form_misleading or "unknown"}'),
        escape_markdown_v2(f'How is it misleading? {result.form_category or "unknown"}'),
        escape_markdown_v2(f'Is it potentially harmful? {result.form_harmful or "unknown"}'),
        "",
        "*Draft Note Text*",
        escape_markdown_preserving_urls(result.draft_note or "Unavailable"),
        "",
        "*Sources*",
    ]

    if result.sources:
        for index, source in enumerate(result.sources, start=1):
            description = source.get("description") or source.get("url") or "Source"
            url = source.get("url", "")
            lines.append(f"{escape_markdown_v2(f'{index}. {description}: ')}{url}")
    else:
        lines.append(escape_markdown_v2("No sources returned."))

    return "\n".join(lines)


def format_parse_failure(raw_text: str) -> str:
    return "\n".join(
        [
            "*Structured parsing failed*",
            "The model returned unstructured output\\. Raw response follows:",
            "",
            escape_markdown_v2(raw_text or "No response text returned."),
        ]
    )
