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
