# Modal Hosting Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the hydration tracker from Railway to Modal so the app runs free within Modal's $30/month Starter credits.

**Architecture:** The Flask app is wrapped as a Modal WSGI web endpoint serving all existing routes unchanged. The two APScheduler cron jobs (daily summaries at 8pm IST, nudges at 1pm IST) are replaced by Modal cron functions that call the same underlying Python functions directly.

**Tech Stack:** Python 3.12, Flask, Modal SDK, Supabase, Meta WhatsApp API, Twilio

---

### Task 1: Install Modal CLI and authenticate

**Files:**
- No file changes — CLI setup only

- [ ] **Step 1: Install Modal in the project virtualenv**

```bash
source .venv/bin/activate
pip install modal
```

Expected output: `Successfully installed modal-X.X.X ...`

- [ ] **Step 2: Authenticate with your Modal account**

```bash
modal token new
```

This opens a browser tab. Log in with your Modal account. You'll see `Token saved` in the terminal when done.

- [ ] **Step 3: Verify auth works**

```bash
modal profile current
```

Expected: your Modal username printed, no errors.

---

### Task 2: Create the Modal secret

**Files:**
- No file changes — Modal dashboard setup

- [ ] **Step 1: Open the Modal secrets dashboard**

Go to https://modal.com/secrets and click **New secret**.

- [ ] **Step 2: Name the secret**

Name it exactly: `hydration-tracker-secrets`

- [ ] **Step 3: Add each key-value pair**

Copy these values from your local `.env` file:

| Key | Where to find the value |
|---|---|
| `SUPABASE_URL` | `.env` line `SUPABASE_URL=...` |
| `SUPABASE_KEY` | `.env` line `SUPABASE_KEY=...` |
| `TWILIO_ACCOUNT_SID` | `.env` line `TWILIO_ACCOUNT_SID=...` |
| `TWILIO_AUTH_TOKEN` | `.env` line `TWILIO_AUTH_TOKEN=...` |
| `TWILIO_WHATSAPP_NUMBER` | `.env` line `TWILIO_WHATSAPP_NUMBER=...` |
| `DAILY_GOAL_ML` | `.env` line `DAILY_GOAL_ML=...` (e.g. `2000`) |
| `ADMIN_PHONE` | `.env` line `ADMIN_PHONE=...` |
| `ADMIN_TOKEN` | `.env` line `ADMIN_TOKEN=...` |

Do not add `META_*` variables — they are stored in Supabase's `settings` table and loaded automatically at runtime.

- [ ] **Step 4: Save the secret**

Click **Save**. Confirm it appears in the secrets list as `hydration-tracker-secrets`.

---

### Task 3: Add modal to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add modal to requirements.txt**

Open `requirements.txt` and add `modal` as a new line at the end:

```
flask==3.0.3
twilio==9.3.3
supabase==2.5.0
python-dotenv==1.0.1
APScheduler==3.10.4
gunicorn==22.0.0
tzdata==2024.1
requests==2.32.3
modal
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "add modal to requirements"
```

---

### Task 4: Move scheduler startup out of module level in main.py

**Files:**
- Modify: `main.py` (lines 689–695)

**Why:** When Modal imports `main.py` to get the Flask app, it runs all module-level code. The scheduler would start inside every Modal container, firing duplicate nudges and summaries. Moving it into `if __name__ == '__main__':` means it only runs when you start the app directly (local dev / Railway), not when Modal imports it.

- [ ] **Step 1: Write a smoke test first**

Create `tests/test_import.py`:

```python
import threading
import os

os.environ.setdefault('SUPABASE_URL', 'https://fake.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'fake-key')
os.environ.setdefault('TWILIO_ACCOUNT_SID', 'ACfake')
os.environ.setdefault('TWILIO_AUTH_TOKEN', 'fake')
os.environ.setdefault('TWILIO_WHATSAPP_NUMBER', '+15005550006')
os.environ.setdefault('ADMIN_PHONE', '+910000000000')


def test_import_does_not_start_scheduler():
    threads_before = {t.name for t in threading.enumerate()}
    import main  # noqa: F401
    threads_after = {t.name for t in threading.enumerate()}
    new_threads = threads_after - threads_before
    scheduler_threads = {t for t in new_threads if 'APScheduler' in t or 'BackgroundScheduler' in t}
    assert not scheduler_threads, f"Scheduler threads started on import: {scheduler_threads}"
```

- [ ] **Step 2: Install pytest and run the test — expect it to FAIL**

```bash
pip install pytest
pytest tests/test_import.py::test_import_does_not_start_scheduler -v
```

Expected: FAIL — the scheduler currently starts on import, so APScheduler threads will be found.

- [ ] **Step 3: Edit main.py — move scheduler into __main__ block**

Find the bottom of `main.py` (around line 688). Replace:

```python
# Use --workers 1 in Procfile to avoid duplicate scheduler jobs across gunicorn workers.
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

With:

```python
if __name__ == '__main__':
    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
    scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
pytest tests/test_import.py::test_import_does_not_start_scheduler -v
```

Expected:
```
PASSED tests/test_import.py::test_import_does_not_start_scheduler
```

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_import.py
git commit -m "move scheduler startup into __main__ so Modal import is safe"
```

---

### Task 5: Create modal_app.py

**Files:**
- Create: `modal_app.py`

- [ ] **Step 1: Create modal_app.py**

Create a new file `modal_app.py` in the project root:

```python
import modal
from main import app as flask_app, send_daily_summaries, send_nudges

modal_app = modal.App("hydration-tracker")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
)

secrets = [modal.Secret.from_name("hydration-tracker-secrets")]


@modal_app.function(image=image, secrets=secrets, schedule=modal.Cron("30 14 * * *"))
def run_daily_summaries():
    send_daily_summaries()


@modal_app.function(image=image, secrets=secrets, schedule=modal.Cron("30 7 * * *"))
def run_nudges():
    send_nudges()


@modal_app.function(image=image, secrets=secrets)
@modal.wsgi_app()
def web():
    return flask_app
```

**Cron schedule notes:**
- `30 14 * * *` = 14:30 UTC = 8:00pm IST (daily summaries)
- `30 7 * * *` = 07:30 UTC = 1:00pm IST (nudges)

- [ ] **Step 2: Verify modal_app.py is syntactically valid**

```bash
python -c "import ast; ast.parse(open('modal_app.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add modal_app.py
git commit -m "add modal_app.py with web endpoint and cron functions"
```

---

### Task 6: Deploy to Modal

**Files:**
- No file changes — deployment step

- [ ] **Step 1: Run a dry-run to check for errors**

```bash
modal deploy modal_app.py --dry-run
```

Expected: Modal prints what it would deploy with no errors. If you see `ModuleNotFoundError` for any package, add it to `requirements.txt` and re-run.

- [ ] **Step 2: Deploy**

```bash
modal deploy modal_app.py
```

Expected output includes something like:
```
✓ Created objects.
├── 🔨 Created run_daily_summaries.
├── 🔨 Created run_nudges.
└── 🔨 Created web.
├── https://<username>--hydration-tracker-web.modal.run ✓
```

- [ ] **Step 3: Copy and save the web URL**

Copy the `https://<username>--hydration-tracker-web.modal.run` URL from the output. You'll need it in the next task.

- [ ] **Step 4: Verify the health endpoint**

```bash
curl https://<your-url>/health
```

Expected: `{"status": "ok"}`

---

### Task 7: Update Meta webhook URL

**Files:**
- No file changes — Meta Developer Console update

- [ ] **Step 1: Open Meta Developer Console**

Go to https://developers.facebook.com → your app → WhatsApp → Configuration.

- [ ] **Step 2: Update the webhook URL**

In the **Webhook** section, change the callback URL to:
```
https://<username>--hydration-tracker-web.modal.run/meta-webhook
```

Leave the verify token as-is (it's still pulled from Supabase).

- [ ] **Step 3: Click Verify and Save**

Meta will send a GET request to `/meta-webhook` with `hub.mode=subscribe`. Your app handles this at the `meta_webhook_verify` route. If verification succeeds, you'll see a green checkmark.

If it fails: check that `META_VERIFY_TOKEN` is correctly set in your Supabase `settings` table and that the Modal deployment is live (`curl https://<your-url>/health` returns 200).

---

### Task 8: End-to-end test

**Files:**
- No file changes — manual verification

- [ ] **Step 1: Send a WhatsApp message to the bot**

Send any message (e.g. `status`) to the WhatsApp number connected to your Meta app.

Expected: The bot replies with your hydration status within a few seconds.

- [ ] **Step 2: Check Modal logs**

```bash
modal app logs hydration-tracker
```

You should see the incoming request logged and the reply sent. No errors.

- [ ] **Step 3: Verify cron functions appear in Modal dashboard**

Go to https://modal.com/apps → hydration-tracker. Confirm `run_daily_summaries` and `run_nudges` are listed with their next scheduled run times.

- [ ] **Step 4: (Optional) Trigger a cron manually to verify it works**

```bash
modal run modal_app.py::run_nudges
```

Expected: nudges are sent to any users who haven't hit 40% of their daily goal. Check Modal logs to confirm.

---

### Task 9: Clean up Railway (when ready)

**Files:**
- No file changes — Railway dashboard

> Do this only after the Modal deployment has been stable for a few days.

- [ ] **Step 1: Go to Railway dashboard**

Open your Railway project and confirm the Modal deployment has been handling traffic correctly.

- [ ] **Step 2: Delete the Railway service**

In Railway → your service → Settings → scroll to bottom → Delete Service.

This stops any further Railway billing once your credits run out.
