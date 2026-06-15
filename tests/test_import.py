import threading
import os

os.environ.setdefault('SUPABASE_URL', 'https://fake.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlIn0.fake_signature')
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
