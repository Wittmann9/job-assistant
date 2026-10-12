import html
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_text(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def send_job(job):
    e = html.escape
    ho = " · 🏠 home office possible" if job.get("homeoffice") else ""
    text = (
        f"🎯 <b>{job['score']}/100</b> — {e(job['title'])}\n"
        f"🏢 {e(job['company'])} · 📍 {e(job['location'])}{ho}\n\n"
        f"{e(job['reason'])}\n\n"
        f"<a href=\"{e(job['url'], quote=True)}\">Open posting</a>"
    )
    send_text(text)