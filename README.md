# WhatsApp Family Hydration Tracker

Family members text their water intake on WhatsApp. The app logs it, replies with a running total, and sends everyone a daily summary at 8 PM IST.

## What family members can send

| Message | Logs |
|---|---|
| `250` or `250ml` | 250 ml |
| `1 glass` / `2 glasses` | 250 ml each |
| `1 bottle` | 500 ml |
| `1 cup` | 150 ml |
| `1 litre` / `1.5 litres` | 1000 ml / 1500 ml |
| `status` | Today's running total |
| `help` | Usage instructions |

---

## 1. Supabase setup

1. Go to [supabase.com](https://supabase.com) → New project.
2. Open **SQL Editor** and run:

```sql
CREATE TABLE users (
    phone         TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    daily_goal_ml INTEGER DEFAULT 2000
);

CREATE TABLE hydration_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_phone  TEXT REFERENCES users(phone),
    amount_ml   INTEGER NOT NULL,
    logged_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hydration_phone_date
    ON hydration_logs(user_phone, logged_at);
```

3. Pre-register your family members (the app auto-creates unknown numbers, but with a generic name):

```sql
INSERT INTO users (phone, name, daily_goal_ml) VALUES
    ('+919876543210', 'Mum',  2000),
    ('+919876543211', 'Dad',  2500),
    ('+919876543212', 'You',  2000);
```

4. Go to **Project Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role** key → `SUPABASE_KEY` (service role lets the app write rows; never expose it in the frontend)

https://tezrsrvgqyeffatuloaw.supabase.co
sb_publishable_wwEEW_GLaphEgFnJuiDprg_Zqyrs15P
curl 'https://api.twilio.com/2010-04-01/Accounts/AC9d1a9d94d9ca29fb6931520df3c89dcc/Messages.json' -X POST \
--data-urlencode 'To=whatsapp:+18578910334' \
--data-urlencode 'From=whatsapp:+14155238886' \
--data-urlencode 'ContentSid=HXb5b62575e6e4ff6129ad7c8efe1f983e' \
--data-urlencode 'ContentVariables={"1":"12/1","2":"3pm"}' \
-u AC9d1a9d94d9ca29fb6931520df3c89dcc:a199beb5202ba856fe37e8b8c9d87f39


---

## 2. Twilio WhatsApp setup

### Sandbox (free, for testing)
1. [console.twilio.com](https://console.twilio.com) → Messaging → Try it out → Send a WhatsApp message.
2. Each family member sends the sandbox join code once (e.g. `join ice-cream`).
3. Copy **Account SID** and **Auth Token** from the Console dashboard.
4. Sandbox number (e.g. `+14155238886`) → `TWILIO_WHATSAPP_NUMBER`.

### Production (optional, after testing)
Request a WhatsApp-enabled number via Twilio's approval process.

---

## 3. Local development

```bash
# Clone / enter the project
cd hydration-tracker

# Create a virtual env
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in secrets
cp .env.example .env
# Edit .env with real values

# Run the dev server
python main.py
```

Expose it to the internet for Twilio to reach it:
```bash
ngrok http 5000
```

Paste the ngrok URL + `/webhook` into Twilio → Messaging → Sandbox → "When a message comes in".

---

## 4. Deploy to Railway

1. Push this folder to a GitHub repo (make sure `.env` is in `.gitignore`).
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Railway auto-detects Python from `requirements.txt` and uses `Procfile` for the start command.
4. Go to **Variables** and add every key from `.env.example` with real values.
5. Railway gives you a public URL (e.g. `https://hydration-tracker-production.up.railway.app`).
6. Set the Twilio webhook URL to: `https://<your-railway-url>/webhook`

> **Important:** Railway auto-assigns `$PORT`. The `Procfile` already uses it — don't hardcode 5000 in Railway.

---

## 5. Environment variables reference

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_WHATSAPP_NUMBER` | Your Twilio WhatsApp number (e.g. `+14155238886`) |
| `DAILY_GOAL_ML` | Default daily goal in ml (default: `2000`) |
| `ADMIN_PHONE` | Your number — receives the full family summary |

---

## 6. Daily summaries

At **8:00 PM IST** every day, each family member gets a personal summary and the admin number gets a full family overview. The scheduler runs inside the same process as the web server (APScheduler). The `Procfile` uses `--workers 1` so only one scheduler instance runs.

---

## 7. Adding family members

Run this SQL in Supabase whenever someone new joins:

```sql
INSERT INTO users (phone, name, daily_goal_ml)
VALUES ('+91xxxxxxxxxx', 'Name', 2000);
```

Phone numbers must include the country code and match the format Twilio sends (`+91...`).
