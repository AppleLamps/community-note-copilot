# Guided Analyst UX Design

**Date:** 2026-04-07

## Goal

Make the Telegram bot feel more interactive and easier to scan without changing the analyzer backend or adding button-heavy state management.

## Product Direction

The bot should behave like a guided analyst rather than a raw formatter. It should:

- acknowledge what the user sent,
- narrate progress in a few short stages,
- return a cleaner result with a strong top summary,
- suggest useful next prompts so the conversation continues naturally,
- fail with recovery guidance instead of raw exceptions.

This stays text-first. No inline keyboards or Telegram reply markup are required for the first pass.

## Scope

### In scope

- richer `/start` and `/help` onboarding copy,
- staged placeholder updates during analysis,
- improved final response layout and labels,
- tailored follow-up suggestions,
- clearer failure messages,
- tests for the new copy and formatting behavior.

### Out of scope

- inline buttons,
- multi-step menus,
- persistent conversation state beyond the existing SQLite history,
- changes to analyzer prompt quality or model behavior.

## UX Flow

### New user

The bot introduces itself clearly, explains what it can accept, and shows example prompts:

- paste a tweet URL,
- paste claim text,
- ask for a revision such as `make it shorter`.

### Analysis request

When a user sends a URL or claim, the bot should:

1. send an immediate acknowledgement,
2. update the same placeholder through 2-3 short stages such as:
   - `Reading the claim...`
   - `Checking sources...`
   - `Drafting a community note...`
3. replace that placeholder with the final answer.

The progress text should be informative but short. It should feel active without becoming noisy.

### Follow-up revision

If the user sends a revision request and prior analysis exists, the bot should acknowledge that it is revising the previous note rather than starting from scratch. The progress text should change accordingly, for example:

- `Reviewing the previous draft...`
- `Rewriting the note...`

### Final answer layout

The response should become easier to scan in Telegram:

- a one-line summary at the top,
- separated sections,
- shorter labels,
- human phrasing instead of internal wording,
- explicit follow-up prompt suggestions at the bottom.

Example section order:

1. Summary
2. Claim
3. Verdict
4. Suggested form selections
5. Draft note
6. Sources
7. Next prompts

### Failure behavior

If analysis fails, the bot should:

- avoid exposing raw exception text as the primary message,
- explain that the analysis could not be completed,
- suggest retrying with the tweet text or asking again,
- log the underlying exception server-side.

## Implementation Notes

- Keep using plain text output to avoid Telegram Markdown parse errors.
- Add a small helper for status text generation in `bot.py`.
- Add a small helper in `formatter.py` for follow-up suggestions based on whether the response is a fresh analysis or revision.
- Prefer deterministic copy over dynamic novelty; this is a utility bot, not a personality demo.

## Testing

Add tests for:

- onboarding copy containing example prompts,
- formatter output containing summary and next prompts,
- follow-up-specific guidance in the final message,
- failure formatting remaining plain text.

## Success Criteria

- The bot visibly communicates progress during analysis.
- The final response is easier to scan on mobile Telegram.
- Users can see what to type next without guessing.
- No Markdown parse issues are reintroduced.
