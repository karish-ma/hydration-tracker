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
