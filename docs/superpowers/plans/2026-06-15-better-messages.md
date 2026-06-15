# Better Messages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the random adjective system with clean name handling, progress-aware motivational phrases, and a visual progress bar in every reply.

**Architecture:** All changes are confined to `main.py`. Three pure functions are added (`progress_bar`, `motivation_phrase`, updated `greeting`). Message templates in `STRINGS` are updated. Dead code (adjective/cheer lists and their helpers) is removed last, after tests pass.

**Tech Stack:** Python 3.12, Flask, pytest

---

### Task 1: Add `progress_bar()` with tests

**Files:**
- Modify: `main.py` — add function after `display_name()` (~line 192)
- Create: `tests/test_messages.py`

- [ ] **Step 1: Create `tests/test_messages.py` with a failing test**

```python
import os
os.environ.setdefault('SUPABASE_URL', 'https://fake.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiJ9.ZopqoUt20nEV8rw6HtnRma8L5xNIANbJHWkKq-3c9Fk')
os.environ.setdefault('TWILIO_ACCOUNT_SID', 'ACfake')
os.environ.setdefault('TWILIO_AUTH_TOKEN', 'fake')
os.environ.setdefault('TWILIO_WHATSAPP_NUMBER', '+15005550006')
os.environ.setdefault('ADMIN_PHONE', '+910000000000')

import main


def test_progress_bar_empty():
    assert main.progress_bar(0) == '▒▒▒▒▒▒▒▒▒▒ 0%'


def test_progress_bar_half():
    assert main.progress_bar(50) == '█████▒▒▒▒▒ 50%'


def test_progress_bar_full():
    assert main.progress_bar(100) == '██████████ 100%'


def test_progress_bar_over_100():
    assert main.progress_bar(110) == '██████████ 110%'


def test_progress_bar_partial():
    assert main.progress_bar(35) == '███▒▒▒▒▒▒▒ 35%'
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/karishmam/Projects/hydration-tracker && source .venv/bin/activate && pytest tests/test_messages.py -v 2>&1 | tail -15
```

Expected: `AttributeError: module 'main' has no attribute 'progress_bar'`

- [ ] **Step 3: Add `progress_bar()` to `main.py` after `display_name()` (~line 192)**

```python
def progress_bar(pct: int) -> str:
    filled = min(10, pct // 10)
    return '█' * filled + '▒' * (10 - filled) + f' {pct}%'
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_messages.py -v 2>&1 | tail -15
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_messages.py && git commit -m "add progress_bar() with tests"
```

---

### Task 2: Add motivation pools to `STRINGS` and `motivation_phrase()` with tests

**Files:**
- Modify: `main.py` — add `import random` at top; add `'motivation'` key to all 3 languages in `STRINGS`; add `motivation_phrase()` after `progress_bar()`
- Modify: `tests/test_messages.py` — add tests

- [ ] **Step 1: Add failing tests to `tests/test_messages.py`**

Append these to the existing file:

```python
def test_motivation_phrase_low_progress_in_pool():
    pool = main.STRINGS['en']['motivation'][0]
    result = main.motivation_phrase('en', 10)
    assert result in pool


def test_motivation_phrase_mid_progress_in_pool():
    pool = main.STRINGS['en']['motivation'][1]
    result = main.motivation_phrase('en', 50)
    assert result in pool


def test_motivation_phrase_high_progress_in_pool():
    pool = main.STRINGS['en']['motivation'][2]
    result = main.motivation_phrase('en', 80)
    assert result in pool


def test_motivation_phrase_goal_reached_in_pool():
    pool = main.STRINGS['en']['motivation'][3]
    result = main.motivation_phrase('en', 100)
    assert result in pool


def test_motivation_phrase_marathi():
    pool = main.STRINGS['mr']['motivation'][0]
    result = main.motivation_phrase('mr', 5)
    assert result in pool


def test_motivation_phrase_german():
    pool = main.STRINGS['de']['motivation'][3]
    result = main.motivation_phrase('de', 100)
    assert result in pool


def test_motivation_phrase_unknown_lang_falls_back_to_english():
    pool = main.STRINGS['en']['motivation'][1]
    result = main.motivation_phrase('xx', 50)
    assert result in pool
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_messages.py -v 2>&1 | tail -20
```

Expected: `AttributeError: module 'main' has no attribute 'motivation_phrase'`

- [ ] **Step 3: Add `import random` at the top of `main.py`**

Find the existing imports block (around line 1) and add `import random` after the stdlib imports:

```python
import os
import re
import random
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
```

- [ ] **Step 4: Add `'motivation'` key to English in `STRINGS`**

In `main.py`, find the `'en'` dict in `STRINGS` and add `'motivation'` as the last key before the closing `}`:

```python
'motivation': [
    [  # 0–25%
        "The first sip is always the hardest. Take it! 💧",
        "Every journey starts somewhere — yours starts now. 🌱",
        "Small start, big finish. Let's go! 💧",
        "Your body is waiting — give it some water! 🌊",
        "No pressure, just a sip. You've got this. 💧",
    ],
    [  # 25–75%
        "You're making it happen — keep going! 💪",
        "Look at you, already halfway there! 🌊",
        "Solid progress. Don't stop now! ⚡",
        "You're in the zone — stay consistent. 🎯",
        "Good work so far. Keep the momentum! 💧",
    ],
    [  # 75–99%
        "So close! Just a little more. 🎯",
        "The finish line is right there — push through! 🏁",
        "Almost done for today. You've got this! 💪",
        "One last stretch — you're nearly there. 🌟",
        "Don't stop now, you're almost at the goal! 🎉",
    ],
    [  # 100%+
        "Goal reached! You did it today! 🎉",
        "Full tank! Your body thanks you. 💙",
        "You crushed your goal today. 🏆",
        "100% done. That's what consistency looks like! 🌟",
        "Hydration goal: complete. Legend status achieved. 💧🎉",
    ],
],
```

- [ ] **Step 5: Add `'motivation'` key to Marathi in `STRINGS`**

Find the `'mr'` dict and add before its closing `}`:

```python
'motivation': [
    [  # 0–25%
        "पहिला घोट सर्वात कठीण असतो — घेऊन टाका! 💧",
        "प्रत्येक प्रवास कुठेतरी सुरू होतो — आत्ता सुरू करा. 🌱",
        "छोटी सुरुवात, मोठा शेवट. चला! 💧",
        "तुमचं शरीर वाट पाहतंय — थोडं पाणी द्या! 🌊",
        "एक छोटासा घोट घ्या — सुरुवात करा! 💧",
    ],
    [  # 25–75%
        "छान चालू आहे — असेच पुढे चला! 💪",
        "बघा, आधीच अर्ध्यावर आलात! 🌊",
        "चांगली प्रगती. थांबू नका! ⚡",
        "तुम्ही लय पकडली आहे — सातत्य ठेवा. 🎯",
        "आतापर्यंत उत्तम काम. असेच चालू ठेवा! 💧",
    ],
    [  # 75–99%
        "इतके जवळ आलात! अजून थोडंसं. 🎯",
        "ध्येय जवळ आहे — शेवटचा प्रयत्न करा! 🏁",
        "आजचं काम जवळजवळ पूर्ण. तुम्ही करू शकता! 💪",
        "थांबू नका, ध्येय दिसतंय! 🌟",
        "शेवटची थोडी घोटं — पूर्ण करा! 🎉",
    ],
    [  # 100%+
        "ध्येय पूर्ण! आज तुम्ही कमाल केली! 🎉",
        "भरलेली टाकी! तुमचं शरीर आभारी आहे. 💙",
        "आजचं लक्ष्य गाठलं. शाबास! 🏆",
        "१००% झालं. हीच सातत्याची ताकद! 🌟",
        "हायड्रेशन ध्येय: पूर्ण. आज खूप छान! 💧🎉",
    ],
],
```

- [ ] **Step 6: Add `'motivation'` key to German in `STRINGS`**

Find the `'de'` dict and add before its closing `}`:

```python
'motivation': [
    [  # 0–25%
        "Der erste Schluck ist immer der schwerste — trink ihn! 💧",
        "Jede Reise beginnt irgendwo — deine beginnt jetzt. 🌱",
        "Klein anfangen, groß enden. Los geht's! 💧",
        "Dein Körper wartet — gib ihm etwas Wasser! 🌊",
        "Kein Druck, nur ein Schluck. Du schaffst das. 💧",
    ],
    [  # 25–75%
        "Du machst das super — weiter so! 💪",
        "Schau mal, schon auf halbem Weg! 🌊",
        "Gute Fortschritte. Nicht aufhören! ⚡",
        "Du bist im Flow — bleib dran. 🎯",
        "Bisher tolle Arbeit. Schwung beibehalten! 💧",
    ],
    [  # 75–99%
        "So nah dran! Noch ein bisschen. 🎯",
        "Die Ziellinie ist gleich da — durch! 🏁",
        "Fast fertig für heute. Du schaffst das! 💪",
        "Nicht aufhören, das Ziel ist in Sicht! 🌟",
        "Noch ein paar Schlucke — du bist fast da! 🎉",
    ],
    [  # 100%+
        "Tagesziel erreicht! Du hast es heute geschafft! 🎉",
        "Voller Tank! Dein Körper dankt dir. 💙",
        "Tagesziel geknackt. Gut gemacht! 🏆",
        "100% geschafft. So sieht Konsequenz aus! 🌟",
        "Hydrationsziel: erledigt. Heute war großartig! 💧🎉",
    ],
],
```

- [ ] **Step 7: Add `motivation_phrase()` to `main.py` after `progress_bar()`**

```python
def motivation_phrase(lang: str, pct: int) -> str:
    pools = STRINGS.get(lang, STRINGS['en'])['motivation']
    if pct >= 100:
        pool = pools[3]
    elif pct >= 75:
        pool = pools[2]
    elif pct >= 25:
        pool = pools[1]
    else:
        pool = pools[0]
    return random.choice(pool)
```

- [ ] **Step 8: Run all tests — expect PASS**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass including the 7 new ones.

- [ ] **Step 9: Commit**

```bash
git add main.py tests/test_messages.py && git commit -m "add motivation phrase pools and motivation_phrase() for all 3 languages"
```

---

### Task 3: Fix `greeting()` and `welcome_message()`

**Files:**
- Modify: `main.py` — update `greeting()` (~line 195) and `welcome_message()` (~line 425); update `welcome` template in all 3 languages in `STRINGS`
- Modify: `tests/test_messages.py` — add tests

- [ ] **Step 1: Add failing tests**

Append to `tests/test_messages.py`:

```python
def test_greeting_named_user():
    user = {'name': 'Aai', 'nick_name': None}
    assert main.greeting(user) == 'Aai'


def test_greeting_nicknamed_user():
    user = {'name': 'Karishma', 'nick_name': 'Aai'}
    assert main.greeting(user) == 'Aai'


def test_greeting_unnamed_user():
    user = {'name': 'User 0334', 'nick_name': None}
    # display_name returns 'User 0334' for auto-generated names — greeting should still return it
    # The real "no name" case is when display_name returns ''
    user2 = {'name': '', 'nick_name': None}
    assert main.greeting(user2) == ''


def test_welcome_message_named_user():
    user = {'name': 'Aai', 'nick_name': None, 'language': 'en', 'daily_goal_ml': 2000}
    msg = main.welcome_message(user)
    assert 'Aai' in msg
    assert 'Hi Aai' in msg


def test_welcome_message_unnamed_user():
    user = {'name': '', 'nick_name': None, 'language': 'en', 'daily_goal_ml': 2000}
    msg = main.welcome_message(user)
    assert 'Hi!' in msg
    assert 'User' not in msg
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_messages.py::test_welcome_message_named_user tests/test_messages.py::test_welcome_message_unnamed_user -v 2>&1 | tail -15
```

Expected: FAIL — `greeting()` currently prepends an adjective, and `welcome_message()` doesn't handle empty names.

- [ ] **Step 3: Update `greeting()` in `main.py`**

Find (around line 195):
```python
def greeting(user: dict) -> str:
    """Returns e.g. 'Lovely Aai' or 'Dear Riya'."""
    return f'{daily_adjective()} {display_name(user)}'
```

Replace with:
```python
def greeting(user: dict) -> str:
    return display_name(user)
```

- [ ] **Step 4: Update `welcome_message()` in `main.py`**

Find (around line 425):
```python
def welcome_message(user: dict) -> str:
    lang = user.get('language') or 'en'
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    return t(lang, 'welcome', name=greeting(user), goal=goal)
```

Replace with:
```python
def welcome_message(user: dict) -> str:
    lang = user.get('language') or 'en'
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    name = greeting(user)
    name_part = f' {name}' if name else ''
    return t(lang, 'welcome', name=name_part, goal=goal)
```

- [ ] **Step 5: Update `welcome` template in all 3 languages — remove the space before `{name}`**

In `STRINGS`, find each `'welcome'` key and change `'Hi {name}!'` → `'Hi{name}!'` (English), `'नमस्कार {name}!'` → `'नमस्कार{name}!'` (Marathi), `'Hallo {name}!'` → `'Hallo{name}!'` (German). The space now lives in `name_part`.

English — find:
```python
'welcome': (
    '💧 Hi {name}! Welcome to your Hydration Tracker!\n\n'
```
Replace with:
```python
'welcome': (
    '💧 Hi{name}! Welcome to your Hydration Tracker!\n\n'
```

Marathi — find:
```python
'welcome': (
    '💧 नमस्कार {name}! तुमच्या हायड्रेशन ट्रॅकरमध्ये स्वागत आहे!\n\n'
```
Replace with:
```python
'welcome': (
    '💧 नमस्कार{name}! तुमच्या हायड्रेशन ट्रॅकरमध्ये स्वागत आहे!\n\n'
```

German — find:
```python
'welcome': (
    '💧 Hallo {name}! Willkommen bei deinem Hydrations-Tracker!\n\n'
```
Replace with:
```python
'welcome': (
    '💧 Hallo{name}! Willkommen bei deinem Hydrations-Tracker!\n\n'
```

- [ ] **Step 6: Run all tests — expect PASS**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_messages.py && git commit -m "fix greeting() to return just name and update welcome_message() for empty name"
```

---

### Task 4: Update message templates and `process_message()`

**Files:**
- Modify: `main.py` — update `'logged'` and `'status'` templates in all 3 languages; update `process_message()` to build `name_part`, `bar`, `motivation` and remove redundant `goal_reached` appending
- Modify: `tests/test_messages.py` — add tests

- [ ] **Step 1: Add failing tests**

Append to `tests/test_messages.py`:

```python
def test_progress_bar_in_logged_template():
    # Verify logged template uses {bar} placeholder
    assert '{bar}' in main.STRINGS['en']['logged']
    assert '{bar}' in main.STRINGS['mr']['logged']
    assert '{bar}' in main.STRINGS['de']['logged']


def test_motivation_in_logged_template():
    assert '{motivation}' in main.STRINGS['en']['logged']


def test_progress_bar_in_status_template():
    assert '{bar}' in main.STRINGS['en']['status']
    assert '{bar}' in main.STRINGS['mr']['status']
    assert '{bar}' in main.STRINGS['de']['status']
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_messages.py::test_progress_bar_in_logged_template tests/test_messages.py::test_motivation_in_logged_template tests/test_messages.py::test_progress_bar_in_status_template -v 2>&1 | tail -10
```

Expected: FAIL — templates don't yet have `{bar}` or `{motivation}`.

- [ ] **Step 3: Update `'logged'` and `'status'` templates in all 3 languages**

In `STRINGS`, make the following replacements:

**English** — find:
```python
'status': '💧 {name}! Today: {total}/{goal}ml ({pct}%)',
'logged': '✅ {name}! Logged {amount}ml. Today: {total}/{goal}ml ({pct}%)',
```
Replace with:
```python
'status': '💧 {name}Today so far:\n{bar}\n{total}/{goal}ml',
'logged': '✅ {name}Logged {amount}ml. {motivation}\n{bar}\n{total}/{goal}ml',
```

**Marathi** — find:
```python
'status': '💧 {name}! आज: {total}/{goal}ml ({pct}%)',
'logged': '✅ {name}! {amount}ml नोंदवले. आज: {total}/{goal}ml ({pct}%)',
```
Replace with:
```python
'status': '💧 {name}आजची प्रगती:\n{bar}\n{total}/{goal}ml',
'logged': '✅ {name}{amount}ml नोंदवले. {motivation}\n{bar}\n{total}/{goal}ml',
```

**German** — find:
```python
'status': '💧 {name}! Heute: {total}/{goal}ml ({pct}%)',
'logged': '✅ {name}! {amount}ml eingetragen. Heute: {total}/{goal}ml ({pct}%)',
```
Replace with:
```python
'status': '💧 {name}Heute bisher:\n{bar}\n{total}/{goal}ml',
'logged': '✅ {name}{amount}ml eingetragen. {motivation}\n{bar}\n{total}/{goal}ml',
```

- [ ] **Step 4: Update `process_message()` — status branch**

Find the `if cmd == 'status':` block (around line 572):
```python
    if cmd == 'status':
        total = get_today_total(phone)
        pct = min(100, int(total / goal * 100))
        return t(lang, 'status', name=greeting(user), total=total, goal=goal, pct=pct)
```

Replace with:
```python
    if cmd == 'status':
        total = get_today_total(phone)
        pct = min(100, int(total / goal * 100))
        name = greeting(user)
        name_part = f'{name}! ' if name else ''
        return t(lang, 'status', name=name_part, total=total, goal=goal, bar=progress_bar(pct), motivation=motivation_phrase(lang, pct))
```

- [ ] **Step 5: Update `process_message()` — log water branch**

Find the section at the bottom of `process_message()` that builds the logged reply (around line 585):
```python
    total = get_today_total(phone)
    pct = min(100, int(total / goal * 100))
    extra = t(lang, 'goal_reached') if total >= goal else ''
    return t(lang, 'logged', name=greeting(user), amount=amount, total=total, goal=goal, pct=pct) + extra
```

Replace with:
```python
    total = get_today_total(phone)
    pct = min(100, int(total / goal * 100))
    name = greeting(user)
    name_part = f'{name}! ' if name else ''
    return t(lang, 'logged', name=name_part, amount=amount, total=total, goal=goal, bar=progress_bar(pct), motivation=motivation_phrase(lang, pct))
```

- [ ] **Step 6: Run all tests — expect PASS**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_messages.py && git commit -m "update logged/status templates with progress bar and contextual motivation"
```

---

### Task 5: Remove dead code

**Files:**
- Modify: `main.py` — delete `ADJECTIVES`, `LOG_CHEERS`, `STATUS_CHEERS`, `_pick()`, `daily_adjective()`, `log_cheer()`, `status_cheer()`

- [ ] **Step 1: Delete the dead code blocks from `main.py`**

Remove the following (all between the imports and `display_name()`):
- The `ADJECTIVES = [...]` list (lines ~82–95)
- The `LOG_CHEERS = [...]` list (lines ~97–142)
- The `STATUS_CHEERS = [...]` list (lines ~144–169)
- The `_pick()` function (lines ~172–175)
- The `daily_adjective()` function (lines ~178–179)
- The `log_cheer()` function (lines ~182–183)
- The `status_cheer()` function (lines ~186–187)

- [ ] **Step 2: Run all tests — expect PASS**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests still pass. If anything references the deleted code, fix it before committing.

- [ ] **Step 3: Commit**

```bash
git add main.py && git commit -m "remove dead adjective and cheer lists and their helper functions"
```

---

### Task 6: Deploy to Modal and verify

**Files:**
- No code changes — deployment only

- [ ] **Step 1: Deploy**

```bash
cd /Users/karishmam/Projects/hydration-tracker && source .venv/bin/activate && modal deploy modal_app.py
```

- [ ] **Step 2: Verify health**

```bash
curl https://karish-ma--hydration-tracker-web.modal.run/health
```

Expected: `{"status": "ok"}`

- [ ] **Step 3: Send a test WhatsApp message**

Send `250` to the bot. Expected reply format:
```
✅ 250ml logged. <motivation phrase>
███▒▒▒▒▒▒▒ 12%
250/2000ml
```

No adjective. No "User XXXX". Progress bar on its own line.
