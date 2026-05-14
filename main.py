import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
DAILY_GOAL_ML = int(os.environ.get('DAILY_GOAL_ML', '2000'))
ADMIN_PHONE = os.environ.get('ADMIN_PHONE', '')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', '')

missing = [k for k, v in {
    'SUPABASE_URL': SUPABASE_URL, 'SUPABASE_KEY': SUPABASE_KEY,
    'TWILIO_ACCOUNT_SID': TWILIO_ACCOUNT_SID, 'TWILIO_AUTH_TOKEN': TWILIO_AUTH_TOKEN,
    'TWILIO_WHATSAPP_NUMBER': TWILIO_WHATSAPP_NUMBER, 'ADMIN_PHONE': ADMIN_PHONE,
}.items() if not v]
if missing:
    logger.warning('Missing environment variables: %s', missing)

IST = ZoneInfo('Asia/Kolkata')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

app = Flask(__name__)

ADJECTIVES = [
    'Dearest', 'Wonderful', 'Lovely', 'Sweetest', 'Amazing',
    'Brilliant', 'Darling', 'Radiant', 'Cherished', 'Fabulous',
    'Dear', 'Precious', 'Sunshine', 'Delightful', 'Incredible',
]

LOG_CHEERS = [
    'Great job logging your water! 💧',
    'Every sip counts — keep it up! 🌊',
    'So proud of you for staying hydrated! 💪',
    'You are doing amazing! 🌟',
    'Keep going, you are on a roll! 🎉',
    'That is the spirit! Hydration goals incoming! 💦',
    'Love seeing you take care of yourself! 🥰',
    'One sip at a time — you have got this! 👏',
    'Fantastic! Your body thanks you! 🙏',
    'Brilliant effort! Stay hydrated, stay glowing! ✨',
]

STATUS_CHEERS = [
    'Here is your update! Keep drinking! 💧',
    'How are you doing today? 🌊',
    'Stay on track, you are doing great! 💪',
    'Check in complete! Keep going! 🌟',
    'Every ml counts! 💦',
]


def daily_adjective() -> str:
    day = datetime.now(IST).timetuple().tm_yday
    return ADJECTIVES[day % len(ADJECTIVES)]


def log_cheer() -> str:
    day = datetime.now(IST).timetuple().tm_yday
    return LOG_CHEERS[day % len(LOG_CHEERS)]


def status_cheer() -> str:
    day = datetime.now(IST).timetuple().tm_yday
    return STATUS_CHEERS[day % len(STATUS_CHEERS)]


def display_name(user: dict) -> str:
    """Returns nick_name if set, else name."""
    return (user.get('nick_name') or user.get('name') or '').strip()


def greeting(user: dict) -> str:
    """Returns e.g. 'Lovely Aai' or 'Dear Riya'."""
    return f'{daily_adjective()} {display_name(user)}'


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


def decimal_suggestion(text: str) -> 'str | None':
    """Catch inputs like .230 or 0.230 (no unit) and suggest the whole number."""
    t = text.strip().lower()
    m = re.match(r'^0?\.(\d+)\s*(?:ml|mls)?$', t)
    if m:
        digits = m.group(1).lstrip('0') or '0'
        return digits
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


def get_or_create_user(phone: str) -> 'tuple[dict, bool]':
    """Returns (user, is_new)."""
    result = supabase.table('users').select('*').eq('phone', phone).execute()
    if result.data:
        return result.data[0], False
    user = {'phone': phone, 'name': f'User {phone[-4:]}', 'nick_name': None, 'daily_goal_ml': DAILY_GOAL_ML}
    supabase.table('users').insert(user).execute()
    return user, True


def send_whatsapp(to: str, body: str) -> None:
    if not to.startswith('whatsapp:'):
        to = f'whatsapp:{to}'
    from_ = TWILIO_WHATSAPP_NUMBER
    if not from_.startswith('whatsapp:'):
        from_ = f'whatsapp:{from_}'
    twilio_client.messages.create(body=body, from_=from_, to=to)


def welcome_message(user: dict) -> str:
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    return (
        f'💧 Hi {greeting(user)}! Welcome to your Hydration Tracker!\n\n'
        f'Your daily goal is *{goal}ml*. Log water by sending:\n'
        '• `250` or `250ml`\n'
        '• `1 glass` (= 250ml)\n'
        '• `1 bottle` (= 500ml)\n'
        '• `1 litre`\n\n'
        "Send `status` to check today's progress. Stay hydrated! 🌊"
    )


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
            f'{greeting(user)}!\n\n'
            f'{bar} {pct}%\n'
            f'Drank: *{total}ml* / {goal}ml\n'
            f'{status}'
        )
        try:
            send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed summary for %s: %s', phone, exc)
        family_lines.append(f'• {display_name(user)}: {total}/{goal}ml ({pct}%)')

    admin_msg = f'👨‍👩‍👧‍👦 *Family Hydration — {today_str}*\n\n' + '\n'.join(family_lines)
    try:
        send_whatsapp(ADMIN_PHONE, admin_msg)
    except Exception as exc:
        logger.error('Failed admin summary: %s', exc)


def send_nudges() -> None:
    logger.info('Sending midday nudges')
    users = supabase.table('users').select('*').execute().data
    for user in users:
        phone = user['phone']
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        total = get_today_total(phone)
        if total >= goal * 0.4:
            continue
        remaining = goal - total
        msg = (
            f'💧 Hey {greeting(user)}! Quick check-in —\n'
            f'You\'ve had *{total}ml* so far today.\n'
            f'Just *{remaining}ml* more to hit your goal. You\'ve got this! 💪'
        )
        try:
            send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed nudge for %s: %s', phone, exc)


@app.route('/add-user', methods=['POST'])
def add_user():
    """
    Pre-register a user so they get a personalized welcome as soon as they've
    joined the Twilio sandbox. Requires X-Admin-Token header if ADMIN_TOKEN is set.

    JSON body:
      phone        – E.164 number, e.g. +919876543210  (required)
      nickname     – what to call them, e.g. "Aai"      (optional)
      name         – fallback display name               (optional)
      daily_goal_ml – override the default goal          (optional)
    """
    if ADMIN_TOKEN and request.headers.get('X-Admin-Token') != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True) or {}
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({'error': 'phone is required'}), 400

    nickname = data.get('nickname', '').strip() or None
    name = data.get('name', '').strip() or (nickname if nickname else f'User {phone[-4:]}')
    goal = int(data.get('daily_goal_ml', DAILY_GOAL_ML))

    existing = supabase.table('users').select('*').eq('phone', phone).execute()
    if existing.data:
        update = {}
        if nickname:
            update['nick_name'] = nickname
        if update:
            supabase.table('users').update(update).eq('phone', phone).execute()
        user = {**existing.data[0], **update}
    else:
        user = {'phone': phone, 'name': name, 'nick_name': nickname, 'daily_goal_ml': goal}
        supabase.table('users').insert(user).execute()

    try:
        send_whatsapp(phone, welcome_message(user))
        return jsonify({'status': 'ok', 'welcome_sent': True})
    except Exception as exc:
        logger.error('Failed to send welcome to %s: %s', phone, exc)
        # User is saved; welcome failed — likely hasn't joined sandbox yet
        return jsonify({'status': 'ok', 'welcome_sent': False, 'error': str(exc)}), 207


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip()
    phone = from_number.replace('whatsapp:', '')

    resp = MessagingResponse()
    reply = resp.message()

    try:
        user, is_new = get_or_create_user(phone)
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        cmd = body.lower()

        if is_new:
            reply.body(welcome_message(user))
            return str(resp)

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
            reply.body(f'💧 {greeting(user)}! {status_cheer()}\nToday: {total}/{goal}ml ({pct}%)')
            return str(resp)

        # Catch decimal-only inputs like .230 or 0.230 before parse_amount
        suggestion = decimal_suggestion(body)
        if suggestion is not None:
            reply.body(f'🤔 Did you mean *{suggestion}ml*? Send `{suggestion}` to log it.')
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
        extra = f'\n🎉 {greeting(user)}! Goal reached today!' if total >= goal else ''
        reply.body(f'✅ {greeting(user)}! {log_cheer()}\nLogged {amount}ml. Today: {total}/{goal}ml ({pct}%){extra}')

    except Exception:
        logger.exception('Webhook error for %s', phone)
        reply.body('⚠️ Something went wrong. Please try again.')

    return str(resp)


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}


# Use --workers 1 in Procfile to avoid duplicate scheduler jobs across gunicorn workers.
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
