import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']
TWILIO_WHATSAPP_NUMBER = os.environ['TWILIO_WHATSAPP_NUMBER']
DAILY_GOAL_ML = int(os.environ.get('DAILY_GOAL_ML', '2000'))
ADMIN_PHONE = os.environ['ADMIN_PHONE']

IST = ZoneInfo('Asia/Kolkata')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

app = Flask(__name__)


def parse_amount(text: str) -> 'int | None':
    t = text.strip().lower()

    m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)$', t)
    if m:
        return max(1, int(float(m.group(1)) * 1000))

    m = re.match(r'^(\d+(?:\.\d+)?)\s*bottles?$', t)
    if m:
        return max(1, int(float(m.group(1)) * 500))

    m = re.match(r'^(\d+(?:\.\d+)?)\s*glasses?$', t)
    if m:
        return max(1, int(float(m.group(1)) * 250))

    m = re.match(r'^(\d+(?:\.\d+)?)\s*cups?$', t)
    if m:
        return max(1, int(float(m.group(1)) * 150))

    # Plain number or with ml: "250", "250ml", "250 ml"
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:ml|mls)?$', t)
    if m:
        val = int(float(m.group(1)))
        return val if val > 0 else None

    return None


def get_today_total(phone: str) -> int:
    today = datetime.now(IST).date()
    start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=IST).isoformat()
    end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=IST).isoformat()
    result = (
        supabase.table('hydration_logs')
        .select('amount_ml')
        .eq('user_phone', phone)
        .gte('logged_at', start)
        .lte('logged_at', end)
        .execute()
    )
    return sum(row['amount_ml'] for row in result.data)


def get_or_create_user(phone: str) -> dict:
    result = supabase.table('users').select('*').eq('phone', phone).execute()
    if result.data:
        return result.data[0]
    user = {'phone': phone, 'name': f'User {phone[-4:]}', 'daily_goal_ml': DAILY_GOAL_ML}
    supabase.table('users').insert(user).execute()
    return user


def send_whatsapp(to: str, body: str) -> None:
    if not to.startswith('whatsapp:'):
        to = f'whatsapp:{to}'
    from_ = TWILIO_WHATSAPP_NUMBER
    if not from_.startswith('whatsapp:'):
        from_ = f'whatsapp:{from_}'
    twilio_client.messages.create(body=body, from_=from_, to=to)


def send_daily_summaries() -> None:
    logger.info('Sending daily summaries')
    today_str = datetime.now(IST).strftime('%d %b %Y')
    users = supabase.table('users').select('*').execute().data
    family_lines = []

    for user in users:
        phone = user['phone']
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        total = get_today_total(phone)
        pct = min(100, int(total / goal * 100))
        bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
        status = '🎉 Goal reached!' if total >= goal else f'Still need {goal - total}ml'
        msg = (
            f'💧 *Daily Summary — {today_str}*\n'
            f'Hi {user["name"]}!\n\n'
            f'{bar} {pct}%\n'
            f'Drank: *{total}ml* / {goal}ml\n'
            f'{status}'
        )
        try:
            send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed summary for %s: %s', phone, exc)
        family_lines.append(f'• {user["name"]}: {total}/{goal}ml ({pct}%)')

    admin_msg = f'👨‍👩‍👧‍👦 *Family Hydration — {today_str}*\n\n' + '\n'.join(family_lines)
    try:
        send_whatsapp(ADMIN_PHONE, admin_msg)
    except Exception as exc:
        logger.error('Failed admin summary: %s', exc)


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip()
    phone = from_number.replace('whatsapp:', '')

    resp = MessagingResponse()
    reply = resp.message()

    try:
        user = get_or_create_user(phone)
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        cmd = body.lower()

        if cmd == 'help':
            reply.body(
                '💧 *Hydration Tracker*\n\n'
                'Log water by sending:\n'
                '• `250` or `250ml`\n'
                '• `1 glass` (= 250ml)\n'
                '• `1 bottle` (= 500ml)\n'
                '• `1 cup` (= 150ml)\n'
                '• `1 litre` or `1.5 litres`\n\n'
                "Send `status` to check today's total."
            )
            return str(resp)

        if cmd == 'status':
            total = get_today_total(phone)
            pct = min(100, int(total / goal * 100))
            reply.body(f'💧 Today: {total}/{goal}ml ({pct}%)')
            return str(resp)

        amount = parse_amount(body)
        if amount is None:
            reply.body("❓ Couldn't understand that. Send `help` for instructions.")
            return str(resp)

        supabase.table('hydration_logs').insert({
            'user_phone': phone,
            'amount_ml': amount,
            'logged_at': datetime.now(IST).isoformat(),
        }).execute()

        total = get_today_total(phone)
        pct = min(100, int(total / goal * 100))
        extra = ' 🎉 Goal reached!' if total >= goal else ''
        reply.body(f'✅ Logged {amount}ml. Today: {total}/{goal}ml ({pct}%){extra}')

    except Exception:
        logger.exception('Webhook error for %s', phone)
        reply.body('⚠️ Something went wrong. Please try again.')

    return str(resp)


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}


# Start scheduler at module level so it runs under both dev server and gunicorn.
# Use --workers 1 in Procfile to avoid duplicate jobs across worker processes.
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
