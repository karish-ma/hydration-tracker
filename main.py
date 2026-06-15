import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests as http_requests
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


def get_setting(key: str, fallback: str = '') -> str:
    try:
        row = supabase.table('settings').select('value').eq('key', key).single().execute()
        return row.data['value'].strip() if row.data else fallback
    except Exception:
        return fallback


META_VERIFY_TOKEN = get_setting('META_VERIFY_TOKEN')
META_ACCESS_TOKEN = get_setting('META_ACCESS_TOKEN')
META_PHONE_NUMBER_ID = get_setting('META_PHONE_NUMBER_ID')
META_WABA_ID = get_setting('META_WABA_ID')


def subscribe_waba():
    if not META_WABA_ID or not META_ACCESS_TOKEN:
        logger.warning('Skipping WABA subscription: META_WABA_ID or META_ACCESS_TOKEN missing')
        return
    try:
        resp = http_requests.post(
            f'https://graph.facebook.com/v19.0/{META_WABA_ID}/subscribed_apps',
            headers={'Authorization': f'Bearer {META_ACCESS_TOKEN}'},
            timeout=10,
        )
        logger.info('WABA subscription: status=%s body=%s', resp.status_code, resp.text)
    except Exception as exc:
        logger.error('WABA subscription failed: %s', exc)


subscribe_waba()

app = Flask(__name__)


@app.before_request
def log_incoming():
    logger.info('Incoming %s %s from %s', request.method, request.path, request.remote_addr)

ADJECTIVES = [
    'Dearest', 'Wonderful', 'Lovely', 'Sweetest', 'Amazing',
    'Brilliant', 'Darling', 'Radiant', 'Cherished', 'Fabulous',
    'Dear', 'Precious', 'Sunshine', 'Delightful', 'Incredible',
    'Glorious', 'Magnificent', 'Stellar', 'Beautiful', 'Superstar',
    'Champion', 'Splendid', 'Phenomenal', 'Extraordinary', 'Spectacular',
    'Beloved', 'Treasured', 'Outstanding', 'Remarkable', 'Dazzling',
    'Vibrant', 'Sparkling', 'Shining', 'Blossoming', 'Unstoppable',
    'Inspiring', 'Heroic', 'Courageous', 'Exceptional', 'Luminous',
    'Joyful', 'Gracious', 'Warm', 'Gentle', 'Triumphant',
    'Resilient', 'Determined', 'Tireless', 'Devoted', 'Golden',
    'Radiant', 'Priceless', 'Braveheart', 'Bright', 'Wholesome',
    'Magnetic', 'Serene', 'Boundless', 'Fearless', 'Heartwarming',
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
    'Your cells are doing a happy dance right now! 💃',
    'That is what I am talking about! Keep it flowing! 🌊',
    'Look at you go! Hydration hero! 🦸',
    'Your future self is already thanking you! 🙏',
    'Water logged! You are unstoppable! 🚀',
    'Small steps, big results — proud of you! 🌱',
    'Sip by sip, you are winning today! 🏆',
    'Body fuelled, spirit lifted — that is the way! ☀️',
    'You just made your kidneys very happy! 💧',
    'Another one down! You are on fire! 🔥',
    'Consistency is your superpower! Keep going! 💫',
    'That sip just brought you one step closer to your goal! 🎯',
    'Hydration game strong! Love to see it! 💪',
    'Health is wealth, and you are investing wisely! 💰',
    'A little water goes a long way — you are proof! 🌿',
    'Your body is glowing from the inside out! ✨',
    'Progress logged! You should be so proud! 🥹',
    'That is the healthy habit we love to see! 🌸',
    'Crushing it one sip at a time! 💥',
    'Wonderful effort! Every drop counts! 🫧',
    'That is pure self-love in a glass! 💙',
    'You showed up for yourself today — that matters! 🌻',
    'Hydrated and thriving — that is you! 🌿',
    'Another sip, another step toward feeling great! 🚶',
    'Your heart, skin, and energy all say thank you! 💛',
    'This is what taking care of yourself looks like! 🫶',
    'Water is medicine and you just took your dose! 💊',
    'Sipping your way to a healthier you! 🌈',
    'That is discipline and love in one gulp! 🏅',
    'Your body deserves this and you delivered! 🎁',
    'Quiet wins are still wins — well done! 🤫✨',
    'You are building something beautiful, one sip at a time! 🏗️',
    'Feeling good starts with exactly this! 🌞',
    'Log after log — you are making it a habit! 🔁',
]

STATUS_CHEERS = [
    'Here is your update! Keep drinking! 💧',
    'Stay on track, you are doing great! 💪',
    'Check in complete! Keep going! 🌟',
    'Every ml counts! 💦',
    'Here is where you stand — you have got this! 🏁',
    'Progress report incoming! 📊',
    'Look how far you have come today! 🌈',
    'Checking in on your hydration journey! 🗺️',
    'Your body keeps the score — here is today\'s tally! 💧',
    'Stay consistent, stay hydrated! 🌊',
    'Here is your hydration snapshot for today! 📸',
    'One sip at a time — here is where you are! 🎯',
    'Proud of you for checking in! 🥹',
    'Knowledge is power — here is your update! ⚡',
    'You asked, I answered — here is your total! 📋',
    'Checking in because you care — love that! 🫶',
    'Here is your daily hydration report! 💧',
    'Still going strong! Here is today so far! 💪',
    'Every check-in is a sign you care — here you go! 🌟',
    'You are paying attention to your health — that is everything! 🫀',
    'Real-time hydration report, just for you! 📡',
    'Here is the honest truth of today so far! 🪞',
    'Numbers do not lie — here is where you are! 📈',
    'Your dedication brought you here to check — love it! 🙌',
]


def _pick(lst: list, extra: int = 0) -> str:
    now = datetime.now(IST)
    idx = (now.timetuple().tm_yday * 24 + now.hour + extra) % len(lst)
    return lst[idx]


def daily_adjective() -> str:
    return _pick(ADJECTIVES)


def log_cheer() -> str:
    return _pick(LOG_CHEERS)


def status_cheer() -> str:
    return _pick(STATUS_CHEERS)


def display_name(user: dict) -> str:
    """Returns nick_name if set, else name."""
    return (user.get('nick_name') or user.get('name') or '').strip()


def progress_bar(pct: int) -> str:
    filled = min(10, pct // 10)
    return '█' * filled + '▒' * (10 - filled) + f' {pct}%'


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

    m = re.match(r'^(\d+(?:\.\d+)?)\s*glass(?:es)?$', t)
    if m:
        return max(1, int(float(m.group(1)) * 250))

    m = re.match(r'^(\d+(?:\.\d+)?)\s*cups?$', t)
    if m:
        return max(1, int(float(m.group(1)) * 150))

    m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:oz|ounces?|fl\.?\s*oz)$', t)
    if m:
        return max(1, int(float(m.group(1)) * 29.57))

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


def send_meta_whatsapp(to: str, body: str) -> None:
    to = to.lstrip('+')
    phone_number_id = META_PHONE_NUMBER_ID
    access_token = META_ACCESS_TOKEN
    resp = http_requests.post(
        f'https://graph.facebook.com/v19.0/{phone_number_id}/messages',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': body},
        },
        timeout=10,
    )
    logger.info('Meta send_whatsapp to=%s status=%s body=%s', to, resp.status_code, resp.text[:300])
    resp.raise_for_status()


def send_meta_whatsapp_template(to: str, template_name: str, params: list) -> None:
    to = to.lstrip('+')
    http_requests.post(
        f'https://graph.facebook.com/v19.0/{META_PHONE_NUMBER_ID}/messages',
        headers={'Authorization': f'Bearer {META_ACCESS_TOKEN}'},
        json={
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': 'en'},
                'components': [{
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in params],
                }],
            },
        },
        timeout=10,
    ).raise_for_status()


LANGUAGE_PICKER = (
    '👋 Welcome! / स्वागत! / Willkommen!\n\n'
    'Choose your language:\n'
    '1. English\n'
    '2. मराठी (Marathi)\n'
    '3. Deutsch (German)'
)

LANGUAGE_CHOICES = {
    '1': 'en', 'english': 'en',
    '2': 'mr', 'marathi': 'mr', 'मराठी': 'mr',
    '3': 'de', 'german': 'de', 'deutsch': 'de',
}

STRINGS = {
    'en': {
        'welcome': (
            '💧 Hi {name}! Welcome to your Hydration Tracker!\n\n'
            'Your daily goal is *{goal}ml*. Log water by sending:\n'
            '• `250` or `250ml`\n'
            '• `1 glass` (= 250ml)\n'
            '• `1 bottle` (= 500ml)\n'
            '• `1 litre`\n\n'
            "Send `status` to check today's progress. Stay hydrated! 🌊"
        ),
        'help': (
            '💧 *Hydration Tracker*\n\n'
            'Log water by sending:\n'
            '• `250` or `250ml`\n'
            '• `1 glass` (= 250ml)\n'
            '• `1 bottle` (= 500ml)\n'
            '• `1 cup` (= 150ml)\n'
            '• `1 litre` or `1.5 litres`\n'
            '• `8 oz` or `8 ounces` (= ~237ml)\n\n'
            "Send `status` to check today's total."
        ),
        'status': '💧 {name}! Today: {total}/{goal}ml ({pct}%)',
        'logged': '✅ {name}! Logged {amount}ml. Today: {total}/{goal}ml ({pct}%)',
        'goal_reached': '\n🎉 Goal reached today!',
        'unknown': '❓ Couldn\'t understand that. Send `help` for instructions.',
        'decimal': '🤔 Did you mean *{suggestion}ml*? Send `{suggestion}` to log it.',
        'language_set': '✅ Language set to English!',
        'thankyou': '😊 You\'re welcome! Keep drinking water! 💧',
    },
    'mr': {
        'welcome': (
            '💧 नमस्कार {name}! तुमच्या हायड्रेशन ट्रॅकरमध्ये स्वागत आहे!\n\n'
            'तुमचे दैनिक लक्ष्य *{goal}ml* आहे. पाणी नोंदवण्यासाठी पाठवा:\n'
            '• `250` किंवा `250ml`\n'
            '• `1 ग्लास` (= 250ml)\n'
            '• `1 बाटली` (= 500ml)\n'
            '• `1 लिटर`\n\n'
            'आजची प्रगती पाहण्यासाठी `status` पाठवा. हायड्रेटेड राहा! 🌊'
        ),
        'help': (
            '💧 *हायड्रेशन ट्रॅकर*\n\n'
            'पाणी नोंदवण्यासाठी पाठवा:\n'
            '• `250` किंवा `250ml`\n'
            '• `1 ग्लास` (= 250ml)\n'
            '• `1 बाटली` (= 500ml)\n'
            '• `1 कप` (= 150ml)\n'
            '• `1 लिटर`\n\n'
            'आजचे एकूण पाहण्यासाठी `status` पाठवा.'
        ),
        'status': '💧 {name}! आज: {total}/{goal}ml ({pct}%)',
        'logged': '✅ {name}! {amount}ml नोंदवले. आज: {total}/{goal}ml ({pct}%)',
        'goal_reached': '\n🎉 आजचे लक्ष्य पूर्ण झाले!',
        'unknown': '❓ समजले नाही. सूचनांसाठी `help` पाठवा.',
        'decimal': '🤔 तुम्हाला *{suggestion}ml* म्हणायचे आहे का? नोंदवण्यासाठी `{suggestion}` पाठवा.',
        'language_set': '✅ भाषा मराठी सेट केली!',
        'thankyou': '😊 आपले स्वागत आहे! पाणी पीत राहा! 💧',
    },
    'de': {
        'welcome': (
            '💧 Hallo {name}! Willkommen bei deinem Hydrations-Tracker!\n\n'
            'Dein tägliches Ziel ist *{goal}ml*. Wasser eintragen:\n'
            '• `250` oder `250ml`\n'
            '• `1 Glas` (= 250ml)\n'
            '• `1 Flasche` (= 500ml)\n'
            '• `1 Liter`\n\n'
            'Sende `status` für deinen heutigen Fortschritt. Bleib hydratisiert! 🌊'
        ),
        'help': (
            '💧 *Hydrations-Tracker*\n\n'
            'Wasser eintragen:\n'
            '• `250` oder `250ml`\n'
            '• `1 Glas` (= 250ml)\n'
            '• `1 Flasche` (= 500ml)\n'
            '• `1 Tasse` (= 150ml)\n'
            '• `1 Liter`\n\n'
            'Sende `status` für dein heutiges Ergebnis.'
        ),
        'status': '💧 {name}! Heute: {total}/{goal}ml ({pct}%)',
        'logged': '✅ {name}! {amount}ml eingetragen. Heute: {total}/{goal}ml ({pct}%)',
        'goal_reached': '\n🎉 Tagesziel heute erreicht!',
        'unknown': '❓ Das habe ich nicht verstanden. Sende `help` für Anweisungen.',
        'decimal': '🤔 Meintest du *{suggestion}ml*? Sende `{suggestion}` zum Eintragen.',
        'language_set': '✅ Sprache auf Deutsch gesetzt!',
        'thankyou': '😊 Gern geschehen! Trink weiter Wasser! 💧',
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    s = STRINGS.get(lang, STRINGS['en']).get(key, STRINGS['en'][key])
    return s.format(**kwargs) if kwargs else s


def welcome_message(user: dict) -> str:
    lang = user.get('language') or 'en'
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    return t(lang, 'welcome', name=greeting(user), goal=goal)


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
        status = '🎉 Goal reached!' if total >= goal else f'Still need {goal - total}ml'
        try:
            if META_PHONE_NUMBER_ID:
                send_meta_whatsapp_template(phone, 'hydration_summary', [
                    today_str, f'{total}ml', f'{goal}ml', status,
                ])
            else:
                bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
                msg = (
                    f'💧 *Daily Summary — {today_str}*\n'
                    f'{greeting(user)}!\n\n'
                    f'{bar} {pct}%\n'
                    f'Drank: *{total}ml* / {goal}ml\n'
                    f'{status}'
                )
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
        try:
            if META_PHONE_NUMBER_ID:
                send_meta_whatsapp_template(phone, 'summary', [
                    greeting(user), f'{total}ml', f'{remaining}ml',
                ])
            else:
                msg = (
                    f'💧 Hey {greeting(user)}! Quick check-in —\n'
                    f'You\'ve had *{total}ml* so far today.\n'
                    f'Just *{remaining}ml* more to hit your goal. You\'ve got this! 💪'
                )
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


def process_message(phone: str, body: str) -> str:
    """Core message logic — shared by Twilio and Meta webhooks. Returns the reply text."""
    user, is_new = get_or_create_user(phone)
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    lang = user.get('language')
    cmd = body.lower().strip()

    # No language set yet — show picker or detect choice
    if not lang:
        choice = LANGUAGE_CHOICES.get(cmd)
        if choice:
            supabase.table('users').update({'language': choice}).eq('phone', phone).execute()
            user['language'] = choice
            return welcome_message(user)
        return LANGUAGE_PICKER

    # Language change command
    if cmd == 'language':
        supabase.table('users').update({'language': None}).eq('phone', phone).execute()
        return LANGUAGE_PICKER

    # Greetings — show welcome/instructions
    if is_new or any(w in cmd for w in ['hi', 'hello', 'hey', 'hii', 'helo', 'hola', 'namaste', 'start']):
        return welcome_message(user)

    # Thank you
    if any(w in cmd for w in ['thank', 'thanks', 'ty', 'thx', '🙏', '😊', '❤️', '🥰', '😍', 'love']):
        return t(lang, 'thankyou')

    if cmd == 'help':
        return t(lang, 'help')

    if cmd == 'status':
        total = get_today_total(phone)
        pct = min(100, int(total / goal * 100))
        return t(lang, 'status', name=greeting(user), total=total, goal=goal, pct=pct)

    suggestion = decimal_suggestion(body)
    if suggestion is not None:
        return t(lang, 'decimal', suggestion=suggestion)

    amount = parse_amount(body)
    if amount is None:
        return t(lang, 'unknown')

    supabase.table('hydration_logs').insert({
        'user_phone': phone,
        'amount_ml': amount,
        'logged_at': datetime.now(IST).isoformat(),
    }).execute()

    total = get_today_total(phone)
    pct = min(100, int(total / goal * 100))
    extra = t(lang, 'goal_reached') if total >= goal else ''
    return t(lang, 'logged', name=greeting(user), amount=amount, total=total, goal=goal, pct=pct) + extra


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip()
    phone = from_number.replace('whatsapp:', '')

    resp = MessagingResponse()
    reply = resp.message()
    try:
        reply.body(process_message(phone, body))
    except Exception:
        logger.exception('Webhook error for %s', phone)
        reply.body('⚠️ Something went wrong. Please try again.')
    return str(resp)


@app.route('/meta-webhook', methods=['GET'])
def meta_webhook_verify():
    if (request.args.get('hub.mode') == 'subscribe'
            and request.args.get('hub.verify_token') == META_VERIFY_TOKEN):
        return request.args.get('hub.challenge'), 200
    return 'Forbidden', 403


@app.route('/meta-webhook', methods=['POST'])
def meta_webhook():
    data = request.get_json(silent=True) or {}
    try:
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                for msg in value.get('messages', []):
                    if msg.get('type') != 'text':
                        continue
                    phone = '+' + msg['from']
                    body = msg.get('text', {}).get('body', '').strip()
                    reply_text = process_message(phone, body)
                    send_meta_whatsapp(phone, reply_text)
    except Exception:
        logger.exception('Meta webhook error')
    return 'OK', 200


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}


@app.route('/privacy', methods=['GET'])
def privacy():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Privacy Policy — Hydration Tracker</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 680px; margin: 60px auto; padding: 0 24px; color: #1e293b; line-height: 1.7; }
    h1 { font-size: 1.6rem; margin-bottom: 4px; }
    h2 { font-size: 1.1rem; margin-top: 32px; }
    p, li { font-size: 0.95rem; color: #334155; }
    a { color: #2563eb; }
  </style>
</head>
<body>
  <h1>💧 Privacy Policy</h1>
  <p><strong>Hydration Tracker</strong> &mdash; Last updated: June 2026</p>

  <h2>What we collect</h2>
  <p>When you message the Hydration Tracker on WhatsApp, we collect and store:</p>
  <ul>
    <li>Your WhatsApp phone number</li>
    <li>The water intake amounts you log</li>
    <li>Timestamps of your messages</li>
  </ul>

  <h2>How we use it</h2>
  <p>Your data is used solely to track your daily water intake, send you progress summaries, and send hydration reminders. We do not use your data for advertising or share it with third parties.</p>

  <h2>Data storage</h2>
  <p>Data is stored securely in Supabase (PostgreSQL). We do not sell or share your personal data.</p>

  <h2>Deleting your data</h2>
  <p>To delete your data, send <strong>delete my data</strong> via WhatsApp or contact us at karishma.mhapadi@gmail.com.</p>

  <h2>Contact</h2>
  <p>Questions? Email <a href="mailto:karishma.mhapadi@gmail.com">karishma.mhapadi@gmail.com</a></p>
</body>
</html>''', 200, {'Content-Type': 'text/html'}


if __name__ == '__main__':
    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_job(send_daily_summaries, 'cron', hour=20, minute=0)
    scheduler.add_job(send_nudges, 'cron', hour=13, minute=0)
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
