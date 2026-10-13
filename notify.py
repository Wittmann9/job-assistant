import html
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def api(method, **payload):
    """Call any Telegram Bot API method."""
    wait = int(payload.get("timeout", 0)) + 30
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        json=payload, timeout=wait,
    )
    r.raise_for_status()
    return r.json()


def send_text(text):
    api("sendMessage", chat_id=CHAT_ID, text=text, parse_mode="HTML",
        disable_web_page_preview=True)


def job_keyboard(job, state=None):
    """Buttons under an alert. state=None -> Save/Skip; otherwise Undo."""
    rows = []
    jid = job["id"]
    if len(jid.encode()) <= 60:  # Telegram limits callback data to 64 bytes
        if state is None:
            rows.append([
                {"text": "💾 Save", "callback_data": f"s|{jid}"},
                {"text": "🚫 Skip", "callback_data": f"k|{jid}"},
            ])
        else:
            rows.append([
                {"text": f"↩ Undo ({state})", "callback_data": f"u|{jid}"},
            ])
    if job.get("url"):
        rows.append([{"text": "🔗 Open listing", "url": job["url"]}])
    return {"inline_keyboard": rows}


def send_job(job):
    e = html.escape
    ho = " · 🏠 home office possible" if job.get("homeoffice") else ""
    text = (
        f"🎯 <b>{job['score']}/100</b> — {e(job['title'])}\n"
        f"🏢 {e(job['company'])} · 📍 {e(job['location'])}{ho}\n\n"
        f"{e(job['reason'])}"
    )
    payload = dict(chat_id=CHAT_ID, text=text, parse_mode="HTML",
                   disable_web_page_preview=True,
                   reply_markup=job_keyboard(job))
    try:
        api("sendMessage", **payload)
    except requests.HTTPError:
        # e.g. Telegram rejected the listing URL: send without the link button
        payload["reply_markup"] = job_keyboard({**job, "url": ""})
        api("sendMessage", **payload)