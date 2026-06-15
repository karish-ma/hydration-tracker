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

Each bracket has a pool of 5–6 phrases. One is picked randomly each time so successive messages feel varied and human.

```python
import random

def motivation_phrase(lang: str, pct: int) -> str:
    pools = STRINGS.get(lang, STRINGS['en'])['motivation']
    if pct >= 100: pool = pools[3]
    elif pct >= 75: pool = pools[2]
    elif pct >= 25: pool = pools[1]
    else: pool = pools[0]
    return random.choice(pool)
```

### Add: `'motivation'` key to each language in `STRINGS`

Each bracket is a **list of 5–6 phrases**, not a single string. Phrases within a bracket are varied in tone and structure so they don't sound like the same sentence reworded.

**English:**
```python
'motivation': [
    [  # 0–25% — gentle nudge to start
        "The first sip is always the hardest. Take it! 💧",
        "Every journey starts somewhere — yours starts now. 🌱",
        "Small start, big finish. Let's go! 💧",
        "Your body is waiting — give it some water! 🌊",
        "No pressure, just a sip. You've got this. 💧",
    ],
    [  # 25–75% — building momentum
        "You're making it happen — keep going! 💪",
        "Look at you, already halfway there! 🌊",
        "Solid progress. Don't stop now! ⚡",
        "You're in the zone — stay consistent. 🎯",
        "Good work so far. Keep the momentum! 💧",
    ],
    [  # 75–99% — almost there
        "So close! Just a little more. 🎯",
        "The finish line is right there — push through! 🏁",
        "Almost done for today. You've got this! 💪",
        "One last stretch — you're nearly there. 🌟",
        "Don't stop now, you're almost at the goal! 🎉",
    ],
    [  # 100%+ — goal reached
        "Goal reached! You did it today! 🎉",
        "Full tank! Your body thanks you. 💙",
        "You crushed your goal today. 🏆",
        "100% done. That's what consistency looks like! 🌟",
        "Hydration goal: complete. Legend status achieved. 💧🎉",
    ],
]
```

**Marathi:**
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
]
```

**German:**
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
