# Guided Analyst UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the Telegram bot into a clearer, more interactive text-first assistant with staged progress updates, cleaner result formatting, and explicit follow-up guidance.

**Architecture:** Keep the existing analyzer and storage flow intact, but improve the user-facing layer in `bot.py` and `formatter.py`. The bot will use deterministic progress-stage copy during request handling and a more structured plain-text formatter for final responses and errors.

**Tech Stack:** Python 3.12, python-telegram-bot, pytest, SQLite

---

### Task 1: Add onboarding and progress copy helpers

**Files:**
- Modify: `E:\telegram-app\community-note-copilot\bot.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_storage.py`

**Step 1: Write the failing test**

Add tests that verify:

- the start/help text includes example prompts,
- progress-stage helper text differs for fresh analysis vs. revision.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -c pytest.ini -v`

Expected: FAIL because the helper or assertions do not exist yet.

**Step 3: Write minimal implementation**

Add deterministic helpers in `bot.py` for:

- richer onboarding copy,
- staged progress messages,
- mode detection for analysis vs. revision.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -c pytest.ini -v`

Expected: PASS

**Step 5: Commit**

```bash
git add bot.py tests/test_storage.py
git commit -m "feat: add guided analyst onboarding and progress copy"
```

### Task 2: Upgrade final response formatting

**Files:**
- Modify: `E:\telegram-app\community-note-copilot\formatter.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_formatter.py`

**Step 1: Write the failing test**

Add tests that verify the final message contains:

- a summary line,
- clearer section headings,
- next prompt suggestions,
- revision-aware guidance when applicable.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_formatter.py -c pytest.ini -v`

Expected: FAIL because the existing formatter does not include these sections.

**Step 3: Write minimal implementation**

Update `formatter.py` to:

- add a compact summary section,
- rename labels to more user-facing language,
- add `Next prompts` suggestions,
- keep the output plain text only.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_formatter.py -c pytest.ini -v`

Expected: PASS

**Step 5: Commit**

```bash
git add formatter.py tests/test_formatter.py
git commit -m "feat: improve telegram result formatting"
```

### Task 3: Wire staged placeholder updates into request handling

**Files:**
- Modify: `E:\telegram-app\community-note-copilot\bot.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_storage.py`

**Step 1: Write the failing test**

Add tests around helper selection so request mode and progress stages are stable and predictable.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -c pytest.ini -v`

Expected: FAIL because the handler support helpers are incomplete.

**Step 3: Write minimal implementation**

Update `message_handler` so it:

- determines whether the request is a fresh analysis or revision before invoking the analyzer,
- edits the placeholder through 2-3 short progress stages,
- uses the upgraded formatter output.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -c pytest.ini -v`

Expected: PASS

**Step 5: Commit**

```bash
git add bot.py tests/test_storage.py
git commit -m "feat: add staged telegram progress updates"
```

### Task 4: Improve failure messaging

**Files:**
- Modify: `E:\telegram-app\community-note-copilot\bot.py`
- Modify: `E:\telegram-app\community-note-copilot\formatter.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_formatter.py`

**Step 1: Write the failing test**

Add a formatter test verifying failure output is user-facing, plain text, and includes retry guidance.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_formatter.py -c pytest.ini -v`

Expected: FAIL because the current failure message is too bare.

**Step 3: Write minimal implementation**

Improve the failure formatter and handler fallback so the user sees:

- that analysis could not be completed,
- what to try next,
- no raw stack-trace-style output.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_formatter.py -c pytest.ini -v`

Expected: PASS

**Step 5: Commit**

```bash
git add bot.py formatter.py tests/test_formatter.py
git commit -m "feat: improve telegram failure recovery messaging"
```

### Task 5: Full verification

**Files:**
- Modify: `E:\telegram-app\community-note-copilot\README.md` if behavior text needs updating
- Test: `E:\telegram-app\community-note-copilot\tests\test_analyzer.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_formatter.py`
- Test: `E:\telegram-app\community-note-copilot\tests\test_storage.py`

**Step 1: Run targeted test suite**

Run: `python -m pytest tests/test_formatter.py tests/test_storage.py -c pytest.ini -v`

Expected: PASS

**Step 2: Run full test suite**

Run: `python -m pytest tests -c pytest.ini -v`

Expected: PASS

**Step 3: Smoke-check application creation**

Run:

```bash
python -c "import os; os.environ['TELEGRAM_BOT_TOKEN']='x'; os.environ['XAI_API_KEY']='y'; from bot import create_application; app=create_application(); print(type(app).__name__)"
```

Expected: `Application`

**Step 4: Commit**

```bash
git add README.md bot.py formatter.py tests
git commit -m "feat: upgrade guided analyst telegram ux"
```
