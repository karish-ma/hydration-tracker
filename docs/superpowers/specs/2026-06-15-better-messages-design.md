# Better Messages Design Spec
_Date: 2026-06-15_

## Problem

The current motivational system picks random adjectives ("Tireless", "Braveheart") from a 60-word list and prepends them to the username, producing messages like "Tireless User 0334!" that feel hollow and absurd. Motivation is completely disconnected from the user's actual progress.

## Goal

Replace the random adjective system with:
1. Clean name handling — just the name, or nothing if no name is set
2. Progress-aware motivational phrases tied to how the user is actually doing
3. A visual progress bar on its own line in every reply

## Changes — all in `main.py`

### Remove entirely
- `ADJECTIVES` list
- `LOG_CHEERS` list
- `STATUS_CHEERS` list
- `_pick()` function
- `daily_adjective()` function
- `log_cheer()` function
- `status_cheer()` function

### Change: `greeting(user)`

Before:
```python
def greeting(user: dict) -> str:
    return f'{daily_adjective()} {display_name(user)}'
```

After:
```python
def greeting(user: dict) -> str:
    return display_name(user)  # empty string if no name set
```

### Add: `progress_bar(pct)`

```python
def progress_bar(pct: int) -> str:
    filled = min(10, pct // 10)
    return '█' * filled + '▒' * (10 - filled) + f' {pct}%'
```

Examples:
- 0%:   `▒▒▒▒▒▒▒▒▒▒ 0%`
- 50%:  `█████▒▒▒▒▒ 50%`
- 100%: `██████████ 100%`

### Add: `motivation_phrase(lang, pct)`

```python
def motivation_phrase(lang: str, pct: int) -> str:
    phrases = STRINGS.get(lang, STRINGS['en'])['motivation']
    if pct >= 100: return phrases[3]
    if pct >= 75:  return phrases[2]
    if pct >= 25:  return phrases[1]
    return phrases[0]
```

### Add: `'motivation'` key to each language in `STRINGS`

**English:**
```python
'motivation': [
    "Every sip counts — let's get started! 💧",
    "You're building momentum — keep it up! 💪",
    "Almost there — one last push! 🎯",
    "Goal reached! You crushed it today! 🎉",
]
```

**Marathi:**
```python
'motivation': [
    "प्रत्येक घोट महत्त्वाचा आहे — सुरुवात करूया! 💧",
    "तुम्ही चांगली प्रगती करत आहात — असेच चालू ठेवा! 💪",
    "जवळजवळ पोहोचलात — शेवटचा प्रयत्न करा! 🎯",
    "ध्येय पूर्ण! आज तुम्ही कमाल केली! 🎉",
]
```

**German:**
```python
'motivation': [
    "Jeder Schluck zählt — fang an! 💧",
    "Du bist auf dem richtigen Weg — weiter so! 💪",
    "Fast geschafft — noch ein letzter Schub! 🎯",
    "Tagesziel erreicht! Großartige Leistung heute! 🎉",
]
```

### Change: message templates in `STRINGS`

The `logged` and `status` templates gain a `{bar}` and `{motivation}` placeholder:

**`logged`** (English example):
```
✅ {name}Logged {amount}ml. {motivation}
{bar}
{total}/{goal}ml
```

**`status`** (English example):
```
💧 {name}Today so far:
{bar}
{total}/{goal}ml
```

The `{name}` placeholder will be `"Aai! "` (with trailing `! `) when a name exists, or `""` when not.

### Change: `process_message()` — build name_part locally

```python
name = greeting(user)
name_part = f"{name}! " if name else ""
pct = min(100, int(total / goal * 100))
bar = progress_bar(pct)
mot = motivation_phrase(lang, pct)
```

Then pass `name=name_part`, `bar=bar`, `motivation=mot` into the `t()` call.

## Example output

**Named user, low progress (Marathi):**
```
✅ Aai! 15ml नोंदवले. प्रत्येक घोट महत्त्वाचा आहे — सुरुवात करूया! 💧
▒▒▒▒▒▒▒▒▒▒ 0%
15/2000ml
```

**Unnamed user, mid progress (English):**
```
✅ 500ml logged. You're building momentum — keep it up! 💪
█████▒▒▒▒▒ 25%
500/2000ml
```

**Named user, goal reached (German):**
```
✅ Riya! 250ml eingetragen. Tagesziel erreicht! Großartige Leistung heute! 🎉
██████████ 100%
2050/2000ml
```

### Change: `welcome_message()`

`welcome_message()` also calls `greeting(user)`. Update it to handle the empty name case:

```python
def welcome_message(user: dict) -> str:
    lang = user.get('language') or 'en'
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    name = greeting(user)
    name_part = f" {name}" if name else ""
    return t(lang, 'welcome', name=name_part, goal=goal)
```

The `welcome` template changes from `'💧 Hi {name}!'` to `'💧 Hi{name}!'` (space moved into `name_part`).
Named user: `"💧 Hi Aai! Welcome..."` — unnamed user: `"💧 Hi! Welcome..."`

## What does NOT change
- `STRINGS` keys for `help`, `unknown`, `decimal`, `language_set`, `thankyou`
- The `send_daily_summaries()` function (already has a progress bar)
- All webhook routes
- Supabase, Twilio, Meta API calls
- Multi-language logic
