from __future__ import annotations

import html
from urllib.parse import urlparse

from analyzer import AnalysisResult


TELEGRAM_MAX = 4096
SAFE_LIMIT = 4000  # leave headroom for HTML tags


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def tag_for_url(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "other"

    if not host:
        return "other"

    if "pacer.uscourts.gov" in host or ".uscourts.gov" in host or "courtlistener.com" in host:
        return "court"
    if "sec.gov" in host:
        return "sec"
    if "fec.gov" in host:
        return "fec"
    if host.endswith(".gov") or ".gov." in host:
        return "gov"
    if host.endswith(".edu") or "pubmed" in host or "nih.gov" in host or "nature.com" in host or "sciencedirect.com" in host or "arxiv.org" in host:
        return "research"
    media_hosts = (
        "nytimes.com",
        "washingtonpost.com",
        "reuters.com",
        "apnews.com",
        "bbc.co.uk",
        "bbc.com",
        "cnn.com",
        "foxnews.com",
        "bloomberg.com",
        "wsj.com",
        "theguardian.com",
    )
    if any(mh in host for mh in media_hosts):
        return "media"
    return "other"


def _build_summary(result: AnalysisResult, request_mode: str) -> str:
    if request_mode == "revision":
        return "<b>Updated draft ready</b>"
    verdict = (result.verdict or "Analysis complete").strip()
    return f"<b>Quick take:</b> {_esc(verdict)}"


def format_analysis_message(result: AnalysisResult, request_mode: str = "analysis") -> str:
    lines: list[str] = [
        _build_summary(result, request_mode),
        "",
        "<b>Claim</b>",
        _esc(result.claim or "Unavailable"),
        "",
        "<b>Verdict</b>",
        _esc(result.verdict or "Unavailable"),
        "",
        "<b>Recommended form selections</b>",
        f"Is this tweet misleading? {_esc(result.form_misleading or 'unknown')}",
        f"How is it misleading? {_esc(result.form_category or 'unknown')}",
        f"Is it potentially harmful? {_esc(result.form_harmful or 'unknown')}",
        "",
        "<b>Suggested Community Note</b> (tap to copy)",
        f"<pre>{_esc(result.draft_note or 'Unavailable')}</pre>",
        "",
        "<b>Sources</b>",
    ]

    if result.sources:
        for index, source in enumerate(result.sources, start=1):
            description = source.get("description") or source.get("url") or "Source"
            url = source.get("url", "")
            tag = tag_for_url(url)
            lines.append(f"{index}. [{tag}] {_esc(description)}: {_esc(url)}")
    else:
        lines.append("No sources returned.")

    return "\n".join(lines)


def format_parse_failure(raw_text: str) -> str:
    return "\n".join(
        [
            "<b>I couldn't finish the analysis.</b>",
            "Try sending the tweet URL again, paste the claim text directly, or ask for a simpler rewrite.",
            "",
            "<b>Details:</b>",
            f"<pre>{_esc(raw_text or 'No response text returned.')}</pre>",
        ]
    )


def split_for_telegram(text: str, limit: int = SAFE_LIMIT) -> list[str]:
    """Split a message into Telegram-safe chunks without breaking <pre>...</pre> blocks."""
    if len(text) <= limit:
        return [text]

    # Walk paragraphs (split on blank lines), greedily packing into chunks.
    # If a single paragraph is itself too large and contains a <pre> block,
    # keep the <pre> block intact and split surrounding text.
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = para if not current else current + "\n\n" + para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        # Paragraph alone exceeds limit. Split on single newlines as a fallback,
        # but don't split inside a <pre>...</pre> region.
        if len(para) <= limit:
            current = para
            continue
        chunks.extend(_hard_split(para, limit))
        current = ""

    if current:
        chunks.append(current)
    return chunks


def _hard_split(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Find a safe break point (newline) before limit, but never inside <pre>.
        cut = remaining.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        # If the cut would land inside a <pre>...</pre>, push past the </pre>.
        head = remaining[:cut]
        if head.count("<pre>") > head.count("</pre>"):
            close = remaining.find("</pre>", cut)
            if close != -1:
                cut = close + len("</pre>")
            else:
                cut = len(remaining)
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        parts.append(remaining)
    return parts
