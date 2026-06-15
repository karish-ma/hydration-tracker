# Modal Hosting Migration — Design Spec
_Date: 2026-06-15_

## Context

The hydration tracker is a Python Flask app currently hosted on Railway (~$5/month after free credits). It uses:
- **Flask** — HTTP server handling WhatsApp webhooks from Meta and Twilio
- **APScheduler** — in-process background scheduler firing daily summaries (8pm IST) and midday nudges (1pm IST)
- **Supabase** — database and settings store
- **Meta WhatsApp Business API** — primary messaging channel
- **Twilio** — secondary messaging channel

The goal is to migrate to Modal (modal.com) for cost reasons: Modal's Starter plan includes $30/month in free compute credits, which is more than sufficient for this app's low traffic and two daily scheduled jobs.

## Architecture

Modal separates the two concerns that currently live in one process:

```
modal_app.py
├── Modal web endpoint     → wraps the existing Flask app (all routes unchanged)
├── Modal cron: summaries  → calls send_daily_summaries() at 8pm IST (14:30 UTC)
└── Modal cron: nudges     → calls send_nudges() at 1pm IST (07:30 UTC)
```

All existing business logic in `main.py` stays untouched. Only the scheduler startup is relocated.

## Files Changed

### `main.py` — one change
Move the APScheduler startup block from module level into `if __name__ == '__main__':` so Modal doesn't accidentally start the scheduler when importing the Flask app.

**Before:**
```python
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

**After:**
```python
if __name__ == '__main__':
    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
    scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

### `modal_app.py` — new file
```python
import modal
from main import app as flask_app, send_daily_summaries, send_nudges

modal_app = modal.App("hydration-tracker")
image = modal.Image.debian_slim().pip_install_from_requirements("requirements.txt")
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

### `requirements.txt` — add Modal
```
modal
```

## Environment Variables

Create a Modal secret named `hydration-tracker-secrets` containing:

| Variable | Source |
|---|---|
| SUPABASE_URL | `.env` |
| SUPABASE_KEY | `.env` |
| TWILIO_ACCOUNT_SID | `.env` |
| TWILIO_AUTH_TOKEN | `.env` |
| TWILIO_WHATSAPP_NUMBER | `.env` |
| DAILY_GOAL_ML | `.env` |
| ADMIN_PHONE | `.env` |
| ADMIN_TOKEN | `.env` |

`META_*` variables are not needed here — they are already stored in Supabase's `settings` table and loaded at runtime.

## Webhook URL

After deploying, Modal provides a stable HTTPS URL:
```
https://<username>--hydration-tracker-web.modal.run
```

Update the Meta Developer Console webhook to:
```
https://<username>--hydration-tracker-web.modal.run/meta-webhook
```

## Deployment Steps (high level)

1. Install Modal CLI and authenticate (`pip install modal && modal token new`)
2. Create the `hydration-tracker-secrets` secret in Modal dashboard
3. Add `modal` to `requirements.txt`
4. Move scheduler startup in `main.py` into `if __name__ == '__main__':`
5. Create `modal_app.py`
6. Deploy: `modal deploy modal_app.py`
7. Copy the generated web URL
8. Update Meta Developer Console with the new webhook URL
9. Verify webhook handshake succeeds
10. Test end-to-end: send a WhatsApp message, confirm reply

## Rollback

Railway deployment stays live until you explicitly delete it. If anything goes wrong after switching the Meta webhook URL, revert the webhook URL in Meta Developer Console back to the Railway URL.
