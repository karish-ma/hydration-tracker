import modal
from main import app as flask_app, send_daily_summaries, send_nudges

app = modal.App("hydration-tracker")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("main")
)

secrets = [modal.Secret.from_name("hydration-tracker-secrets")]


@app.function(image=image, secrets=secrets, schedule=modal.Cron("30 14 * * *"))
def run_daily_summaries():
    send_daily_summaries()


@app.function(image=image, secrets=secrets, schedule=modal.Cron("30 7 * * *"))
def run_nudges():
    send_nudges()


@app.function(image=image, secrets=secrets, keep_warm=1)
@modal.wsgi_app()
def web():
    return flask_app
