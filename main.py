import os
import re
import random
import logging
from datetime import datetime, timedelta
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

COUNTRY_TIMEZONES: dict[str, str] = {
    '1':   'America/New_York',
    '7':   'Europe/Moscow',
    '20':  'Africa/Cairo',
    '27':  'Africa/Johannesburg',
    '30':  'Europe/Athens',
    '31':  'Europe/Amsterdam',
    '32':  'Europe/Brussels',
    '33':  'Europe/Paris',
    '34':  'Europe/Madrid',
    '36':  'Europe/Budapest',
    '39':  'Europe/Rome',
    '40':  'Europe/Bucharest',
    '41':  'Europe/Zurich',
    '43':  'Europe/Vienna',
    '44':  'Europe/London',
    '45':  'Europe/Copenhagen',
    '46':  'Europe/Stockholm',
    '47':  'Europe/Oslo',
    '48':  'Europe/Warsaw',
    '49':  'Europe/Berlin',
    '51':  'America/Lima',
    '52':  'America/Mexico_City',
    '54':  'America/Argentina/Buenos_Aires',
    '55':  'America/Sao_Paulo',
    '56':  'America/Santiago',
    '57':  'America/Bogota',
    '60':  'Asia/Kuala_Lumpur',
    '61':  'Australia/Sydney',
    '62':  'Asia/Jakarta',
    '63':  'Asia/Manila',
    '64':  'Pacific/Auckland',
    '65':  'Asia/Singapore',
    '66':  'Asia/Bangkok',
    '81':  'Asia/Tokyo',
    '82':  'Asia/Seoul',
    '84':  'Asia/Ho_Chi_Minh',
    '86':  'Asia/Shanghai',
    '90':  'Europe/Istanbul',
    '91':  'Asia/Kolkata',
    '92':  'Asia/Karachi',
    '94':  'Asia/Colombo',
    '98':  'Asia/Tehran',
    '212': 'Africa/Casablanca',
    '213': 'Africa/Algiers',
    '216': 'Africa/Tunis',
    '218': 'Africa/Tripoli',
    '234': 'Africa/Lagos',
    '254': 'Africa/Nairobi',
    '255': 'Africa/Dar_es_Salaam',
    '256': 'Africa/Kampala',
    '880': 'Asia/Dhaka',
    '966': 'Asia/Riyadh',
    '971': 'Asia/Dubai',
    '972': 'Asia/Jerusalem',
    '977': 'Asia/Kathmandu',
}


def timezone_for_phone(phone: str) -> ZoneInfo:
    """Infer timezone from E.164 country-code prefix (+1 → US/ET, +91 → India, etc.)."""
    digits = phone.lstrip('+')
    for length in (3, 2, 1):
        code = digits[:length]
        if code in COUNTRY_TIMEZONES:
            return ZoneInfo(COUNTRY_TIMEZONES[code])
    return IST


def get_user_tz(user: dict) -> ZoneInfo:
    """Return the user's timezone: stored preference first, then phone-number inference."""
    tz_str = user.get('timezone')
    if tz_str:
        try:
            return ZoneInfo(tz_str)
        except Exception:
            pass
    return timezone_for_phone(user['phone'])

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

def display_name(user: dict) -> str:
    """Returns nick_name if set, else name."""
    return (user.get('nick_name') or user.get('name') or '').strip()


def progress_bar(pct: int) -> str:
    filled = min(10, pct // 10)
    return '█' * filled + '▒' * (10 - filled) + f' {pct}%'


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


def greeting(user: dict) -> str:
    return display_name(user)


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
    tz = timezone_for_phone(phone)
    today = datetime.now(tz).date()
    start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz).isoformat()
    end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=tz).isoformat()
    result = (
        supabase.table('hydration_logs')
        .select('amount_ml')
        .eq('user_phone', phone)
        .gte('logged_at', start)
        .lte('logged_at', end)
        .execute()
    )
    return sum(row['amount_ml'] for row in result.data)


def get_yesterday_total(phone: str) -> int:
    tz = timezone_for_phone(phone)
    yesterday = (datetime.now(tz) - timedelta(days=1)).date()
    start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=tz).isoformat()
    end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=tz).isoformat()
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
            '💧 Hi{name}! Welcome to your Hydration Tracker!\n\n'
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
        'status': '💧 {name}Today so far:\n{bar}\n{total}/{goal}ml',
        'logged': '✅ {name}Logged {amount}ml. {motivation}\n{bar}\n{total}/{goal}ml',
        'goal_reached': '\n🎉 Goal reached today!',
        'unknown': '❓ Couldn\'t understand that. Send `help` for instructions.',
        'decimal': '🤔 Did you mean *{suggestion}ml*? Send `{suggestion}` to log it.',
        'language_set': '✅ Language set to English!',
        'thankyou': '😊 You\'re welcome! Keep drinking water! 💧',
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
        'morning_recap': {
            'greeting': 'Good morning{name}! ☀️',
            'stat': 'Yesterday you drank *{total}ml* out of your {goal}ml goal.',
            'over': [
                "You hit {actual_pct}% — {over}% beyond your goal. That's not discipline, that's dedication. 🏆 Same energy today?",
                "Full tank and then some! {over}% over target. Your body is loving you right now. Let's go again. 💧🔥",
                "Overachiever alert! {total}ml — {over}% above goal. Today, same energy. ⚡",
                "Yesterday you didn't just meet the bar — you raised it. {actual_pct}%. Can you top it? 🚀",
                "{over}% over goal. You made it look easy. Keep that streak alive today. 💪",
            ],
            'exact': [
                "Exactly on goal — perfectly on point. 🎯 Let's do it again.",
                "Hit your {goal}ml target exactly. Clean. Precise. Now do it again. 💧",
                "Perfect score! {goal}ml logged. Today's goal? Same thing. 🏆",
            ],
            'close': [
                "So close yesterday — just {shortfall}ml away from your goal. Today, let's close it out. 🎯",
                "{actual_pct}% of your goal — nearly there! That {shortfall}ml gap? Let's kill it today. 💪",
                "You were {shortfall}ml away from the finish line yesterday. Make today the day. 🌊",
                "{actual_pct}% — solid effort! A little more focus today and you're over the line. 🏁",
                "Almost had it! {shortfall}ml stood between you and 100%. Not today. 💧",
            ],
            'half': [
                "Past the halfway mark! Let's see what happens when you go all in today. 🌊",
                "{total}ml logged — you showed up. Now let's double down. Your goal is {goal}ml. 💪",
                "{actual_pct}% is progress. Progress builds habit. Today, aim for the full {goal}ml. 🎯",
                "Good start yesterday. Every sip counts — let's make today count even more. ⚡",
                "Halfway there. Push past the line today — you're more capable than yesterday's score. 💧",
            ],
            'low': [
                "Yesterday was a dry day. No judgment — just a nudge. Today's wide open. 💧",
                "Your body was probably asking for more yesterday. Listen to it today! 🌊",
                "We all have off days. Yesterday was one. Fresh start today — let's make it count. 💪",
                "Only {actual_pct}% yesterday — that makes today your comeback day. Ready? 🔥",
                "Your goal is {goal}ml. Yesterday you got {actual_pct}% there. Today, let's flip the story. 🚀",
            ],
        },
    },
    'mr': {
        'welcome': (
            '💧 नमस्कार{name}! तुमच्या हायड्रेशन ट्रॅकरमध्ये स्वागत आहे!\n\n'
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
        'status': '💧 {name}आजची प्रगती:\n{bar}\n{total}/{goal}ml',
        'logged': '✅ {name}{amount}ml नोंदवले. {motivation}\n{bar}\n{total}/{goal}ml',
        'goal_reached': '\n🎉 आजचे लक्ष्य पूर्ण झाले!',
        'unknown': '❓ समजले नाही. सूचनांसाठी `help` पाठवा.',
        'decimal': '🤔 तुम्हाला *{suggestion}ml* म्हणायचे आहे का? नोंदवण्यासाठी `{suggestion}` पाठवा.',
        'language_set': '✅ भाषा मराठी सेट केली!',
        'thankyou': '😊 आपले स्वागत आहे! पाणी पीत राहा! 💧',
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
        'morning_recap': {
            'greeting': 'शुभ सकाळ{name}! ☀️',
            'stat': 'काल तुम्ही *{total}ml* प्यायलात (लक्ष्य: {goal}ml).',
            'over': [
                "तुम्ही {actual_pct}% गाठलं — लक्ष्यापेक्षा {over}% जास्त! हीच ऊर्जा आज ठेवा. 🏆",
                "कमाल! {over}% जास्त पाणी प्यायलात. आज पुन्हा तेच करूया. 💧🔥",
                "लक्ष्यापेक्षा {over}% अधिक! तुमचं शरीर आभारी आहे. आज पण असंच! ⚡",
                "काल बार उंचावलात — {actual_pct}%! आज आणखी उंच जाऊ का? 🚀",
                "{over}% जास्त — सहज केलंत. हा सिलसिला कायम ठेवा. 💪",
            ],
            'exact': [
                "अगदी बरोब्बर {goal}ml — परफेक्ट! 🎯 आज पुन्हा करा.",
                "लक्ष्य अचूक गाठलं. स्वच्छ. नेमकं. आता पुन्हा करा. 💧",
                "शंभर टक्के! आज पण तेच ध्येय. 🏆",
            ],
            'close': [
                "इतके जवळ होतात — फक्त {shortfall}ml दूर! आज ते अंतर भरूया. 🎯",
                "{actual_pct}% — जवळजवळ पूर्ण! तो {shortfall}ml चा फरक आज संपवा. 💪",
                "{shortfall}ml दूर होतात यशापासून. आज तो क्षण येऊ द्या. 🌊",
                "{actual_pct}% — उत्तम प्रयत्न! आज थोडी जास्त मेहनत आणि लक्ष्य पार. 🏁",
                "जवळजवळ झालं होतं! {shortfall}ml राहिले होते. आज नाही राहणार. 💧",
            ],
            'half': [
                "अर्ध्यावर पोहोचलात! आज पूर्ण करण्याची वेळ आहे. 🌊",
                "{total}ml नोंदवलं — सुरुवात केली. आता दुप्पट करूया. लक्ष्य {goal}ml आहे. 💪",
                "{actual_pct}% म्हणजे प्रगती. प्रगती सवयी बनवते. आज {goal}ml चं लक्ष्य गाठा. 🎯",
                "काल चांगली सुरुवात झाली. आज आणखी पुढे जाऊया. ⚡",
                "अर्धा पल्ला मारला. आज पूर्ण पल्ला मारायचा आहे. 💧",
            ],
            'low': [
                "काल कमी झालं. ठीक आहे — आज नवी सुरुवात आहे. 💧",
                "काल शरीराला जास्त पाणी हवं होतं. आज त्याचं ऐका! 🌊",
                "प्रत्येकाचे वाईट दिवस येतात. आज मात्र वेगळं करूया. 💪",
                "फक्त {actual_pct}% काल — आज कमबॅक करायचा आहे. तयार? 🔥",
                "लक्ष्य {goal}ml आहे. काल {actual_pct}% झालं. आज वेगळी कहाणी लिहूया. 🚀",
            ],
        },
    },
    'de': {
        'welcome': (
            '💧 Hallo{name}! Willkommen bei deinem Hydrations-Tracker!\n\n'
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
        'status': '💧 {name}Heute bisher:\n{bar}\n{total}/{goal}ml',
        'logged': '✅ {name}{amount}ml eingetragen. {motivation}\n{bar}\n{total}/{goal}ml',
        'goal_reached': '\n🎉 Tagesziel heute erreicht!',
        'unknown': '❓ Das habe ich nicht verstanden. Sende `help` für Anweisungen.',
        'decimal': '🤔 Meintest du *{suggestion}ml*? Sende `{suggestion}` zum Eintragen.',
        'language_set': '✅ Sprache auf Deutsch gesetzt!',
        'thankyou': '😊 Gern geschehen! Trink weiter Wasser! 💧',
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
        'morning_recap': {
            'greeting': 'Guten Morgen{name}! ☀️',
            'stat': 'Gestern hast du *{total}ml* von deinem {goal}ml-Ziel getrunken.',
            'over': [
                "Du hast {actual_pct}% erreicht — {over}% über deinem Ziel. Das ist echte Hingabe. 🏆 Gleiche Energie heute?",
                "Volltank und mehr! {over}% über dem Ziel. Dein Körper liebt dich. Nochmal! 💧🔥",
                "Übererfüllt! {total}ml — {over}% über Ziel. Heute dieselbe Energie. ⚡",
                "Gestern die Latte höhergelegt — {actual_pct}%! Kannst du das toppen? 🚀",
                "{over}% über Ziel. Einfach gemacht. Halt den Lauf aufrecht. 💪",
            ],
            'exact': [
                "Genau auf Ziel — präzise! 🎯 Mach's nochmal.",
                "Exakt {goal}ml getroffen. Sauber. Genau. Und nochmal. 💧",
                "100%! Heute dasselbe Ziel. 🏆",
            ],
            'close': [
                "So nah — nur {shortfall}ml gefehlt! Heute schließen wir die Lücke. 🎯",
                "{actual_pct}% — fast geschafft! Die {shortfall}ml Lücke? Heute eliminieren wir sie. 💪",
                "Nur {shortfall}ml von der Ziellinie entfernt. Heute ist der Tag. 🌊",
                "{actual_pct}% — tolle Leistung! Noch etwas mehr Fokus heute und du bist drüber. 🏁",
                "Fast! Nur {shortfall}ml zwischen dir und 100%. Nicht heute. 💧",
            ],
            'half': [
                "Über die Hälfte! Mal sehen was passiert, wenn du heute alles gibst. 🌊",
                "{total}ml getrunken — du warst dabei. Jetzt verdoppeln. Dein Ziel: {goal}ml. 💪",
                "{actual_pct}% ist Fortschritt. Fortschritt baut Gewohnheiten. Heute: volle {goal}ml. 🎯",
                "Guter Start gestern. Heute noch mehr draus machen. ⚡",
                "Halbzeit. Heute über die Linie — du kannst mehr als gestern. 💧",
            ],
            'low': [
                "Gestern war es wenig. Kein Problem — heute ist ein neuer Tag. 💧",
                "Dein Körper hat gestern mehr gewollt. Heute auf ihn hören! 🌊",
                "Jeder hat schlechte Tage. Gestern war einer davon. Heute zählt. 💪",
                "Nur {actual_pct}% gestern — heute ist dein Comeback-Tag. Bereit? 🔥",
                "Dein Ziel: {goal}ml. Gestern: {actual_pct}%. Heute schreiben wir eine andere Geschichte. 🚀",
            ],
        },
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    s = STRINGS.get(lang, STRINGS['en']).get(key, STRINGS['en'][key])
    return s.format(**kwargs) if kwargs else s


def welcome_message(user: dict) -> str:
    lang = user.get('language') or 'en'
    goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
    name = greeting(user)
    name_part = f' {name}' if name else ''
    return t(lang, 'welcome', name=name_part, goal=goal)


def send_morning_recap() -> None:
    logger.info('Sending morning recaps (hourly sweep)')
    users = supabase.table('users').select('*').execute().data
    for user in users:
        phone = user['phone']
        tz = get_user_tz(user)
        local_now = datetime.now(tz)

        if local_now.hour != 8:
            continue

        today_date = local_now.strftime('%Y-%m-%d')
        result = (
            supabase.table('users')
            .update({'last_recap_date': today_date})
            .eq('phone', phone)
            .or_(f'last_recap_date.is.null,last_recap_date.neq.{today_date}')
            .execute()
        )
        if not result.data:
            logger.info('Morning recap already sent today for %s, skipping', phone)
            continue

        lang = user.get('language') or 'en'
        mr = STRINGS.get(lang, STRINGS['en'])['morning_recap']
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        yesterday_total = get_yesterday_total(phone)
        actual_pct = int(yesterday_total / goal * 100)
        shortfall = goal - yesterday_total
        over = actual_pct - 100
        name = greeting(user)

        fmt = dict(actual_pct=actual_pct, over=over, shortfall=shortfall, total=yesterday_total, goal=goal)

        if actual_pct >= 100 and over > 0:
            recap = random.choice(mr['over']).format(**fmt)
        elif actual_pct >= 100:
            recap = random.choice(mr['exact']).format(**fmt)
        elif actual_pct >= 75:
            recap = random.choice(mr['close']).format(**fmt)
        elif actual_pct >= 50:
            recap = random.choice(mr['half']).format(**fmt)
        else:
            recap = random.choice(mr['low']).format(**fmt)

        greeting_line = mr['greeting'].format(name=f', {name}' if name else '')
        msg = (
            f'{greeting_line}\n\n'
            f'{mr["stat"].format(**fmt)}\n'
            f'{recap}'
        )

        try:
            if META_PHONE_NUMBER_ID:
                send_meta_whatsapp(phone, msg)
            else:
                send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed morning recap for %s: %s', phone, exc)
            # Reset so next hourly run can retry
            supabase.table('users').update({'last_recap_date': None}).eq('phone', phone).execute()


def send_daily_summaries() -> None:
    logger.info('Sending daily summaries (hourly sweep)')
    users = supabase.table('users').select('*').execute().data
    family_lines = []

    for user in users:
        phone = user['phone']
        tz = get_user_tz(user)
        local_now = datetime.now(tz)

        # Only send at 8pm in the user's local timezone
        if local_now.hour != 20:
            continue

        today_str = local_now.strftime('%d %b %Y')
        today_date = local_now.strftime('%Y-%m-%d')

        # Atomically mark as sent — skip if already sent today (prevents duplicate sends if cron runs twice)
        result = (
            supabase.table('users')
            .update({'last_summary_date': today_date})
            .eq('phone', phone)
            .or_(f'last_summary_date.is.null,last_summary_date.neq.{today_date}')
            .execute()
        )
        if not result.data:
            logger.info('Summary already sent today for %s, skipping', phone)
            continue

        lang = user.get('language') or 'en'
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        total = get_today_total(phone)
        actual_pct = int(total / goal * 100)
        bar_pct = min(100, actual_pct)

        if actual_pct >= 100:
            over = actual_pct - 100
            status = f'🏆 You crushed it — {over}% over your goal!' if over > 0 else '🏆 Exactly on goal — perfect!'
        elif actual_pct >= 50:
            remaining = goal - total
            status = f'Almost there! Just {remaining}ml to go 💪'
        else:
            remaining = goal - total
            status = f'Still {remaining}ml to go — let\'s finish strong! 💧'

        motivation = motivation_phrase(lang, bar_pct)

        try:
            if META_PHONE_NUMBER_ID:
                send_meta_whatsapp_template(phone, 'hydration_summary', [
                    today_str, f'{total}ml', f'{goal}ml', status,
                ])
            else:
                bar = '█' * (bar_pct // 10) + '░' * (10 - bar_pct // 10)
                msg = (
                    f'💧 *Daily Summary — {today_str}*\n'
                    f'{greeting(user)}!\n\n'
                    f'{bar} {bar_pct}%\n'
                    f'Drank: *{total}ml* / {goal}ml\n'
                    f'{status}\n'
                    f'{motivation}'
                )
                send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed summary for %s: %s', phone, exc)
        family_lines.append(f'• {display_name(user)}: {total}/{goal}ml ({actual_pct}%)')

    if family_lines:
        admin_msg = f'👨‍👩‍👧‍👦 *Family Hydration*\n\n' + '\n'.join(family_lines)
        try:
            send_whatsapp(ADMIN_PHONE, admin_msg)
        except Exception as exc:
            logger.error('Failed admin summary: %s', exc)


def send_nudges() -> None:
    logger.info('Sending midday nudges (hourly sweep)')
    users = supabase.table('users').select('*').execute().data
    for user in users:
        phone = user['phone']
        tz = get_user_tz(user)
        local_now = datetime.now(tz)

        # Only send at 1pm in the user's local timezone
        if local_now.hour != 13:
            continue

        today_date = local_now.strftime('%Y-%m-%d')
        goal = user.get('daily_goal_ml') or DAILY_GOAL_ML
        total = get_today_total(phone)
        if total >= goal * 0.4:
            continue
        result = (
            supabase.table('users')
            .update({'last_nudge_date': today_date})
            .eq('phone', phone)
            .or_(f'last_nudge_date.is.null,last_nudge_date.neq.{today_date}')
            .execute()
        )
        if not result.data:
            logger.info('Nudge already sent today for %s, skipping', phone)
            continue
        remaining = goal - total
        msg = (
            f'💧 Hey {greeting(user)}! Quick check-in —\n'
            f'You\'ve had *{total}ml* so far today.\n'
            f'Just *{remaining}ml* more to hit your goal. You\'ve got this! 💪'
        )
        try:
            if META_PHONE_NUMBER_ID:
                send_meta_whatsapp(phone, msg)
            else:
                send_whatsapp(phone, msg)
        except Exception as exc:
            logger.error('Failed nudge for %s: %s', phone, exc)
            supabase.table('users').update({'last_nudge_date': None}).eq('phone', phone).execute()


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

    # Timezone command: "timezone IST" or "timezone Asia/Kolkata"
    TIMEZONE_ALIASES = {
        'ist': 'Asia/Kolkata', 'india': 'Asia/Kolkata',
        'gmt': 'UTC', 'utc': 'UTC',
        'est': 'America/New_York', 'edt': 'America/New_York',
        'cst': 'America/Chicago', 'cdt': 'America/Chicago',
        'pst': 'America/Los_Angeles', 'pdt': 'America/Los_Angeles',
        'gst': 'Asia/Dubai', 'uae': 'Asia/Dubai',
        'pkt': 'Asia/Karachi', 'bst': 'Asia/Dhaka',
        'sgt': 'Asia/Singapore', 'jst': 'Asia/Tokyo',
    }
    if cmd.startswith('timezone ') or cmd.startswith('tz '):
        tz_arg = body.strip().split(None, 1)[1].strip()
        tz_str = TIMEZONE_ALIASES.get(tz_arg.lower(), tz_arg)
        try:
            ZoneInfo(tz_str)
            supabase.table('users').update({'timezone': tz_str}).eq('phone', phone).execute()
            return f'✅ Timezone set to {tz_str}. Your daily messages will now arrive at the right times!'
        except Exception:
            return f'❓ Unknown timezone "{tz_arg}". Try `timezone IST`, `timezone Asia/Kolkata`, etc.'

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
        name = greeting(user)
        name_part = f'{name}! ' if name else ''
        return t(lang, 'status', name=name_part, total=total, goal=goal, bar=progress_bar(pct), motivation=motivation_phrase(lang, pct))

    suggestion = decimal_suggestion(body)
    if suggestion is not None:
        return t(lang, 'decimal', suggestion=suggestion)

    amount = parse_amount(body)
    if amount is None:
        return t(lang, 'unknown')

    supabase.table('hydration_logs').insert({
        'user_phone': phone,
        'amount_ml': amount,
        'logged_at': datetime.now(get_user_tz(user)).isoformat(),
    }).execute()

    total = get_today_total(phone)
    pct = min(100, int(total / goal * 100))
    name = greeting(user)
    name_part = f'{name}! ' if name else ''
    return t(lang, 'logged', name=name_part, amount=amount, total=total, goal=goal, bar=progress_bar(pct), motivation=motivation_phrase(lang, pct))


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
    scheduler = BackgroundScheduler(timezone='UTC')
    scheduler.add_job(send_morning_recap, 'cron', minute=0)
    scheduler.add_job(send_daily_summaries, 'cron', minute=0)
    scheduler.add_job(send_nudges, 'cron', minute=0)
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
