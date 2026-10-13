import argparse
import html
import os
import time
from collections import Counter

from dotenv import load_dotenv

import db
from notify import api, job_keyboard, send_text

load_dotenv()
CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip()
STATS = Counter()

HELP = (
    "<b>Job assistant</b>\n"
    "/saved – your saved jobs\n"
    "/stats – overview of what was found\n"
    "Use the buttons under each alert to save or skip a job."
)


def format_saved(conn):
    rows = db.list_by_status(conn, "saved", 15)
    if not rows:
        return "No saved jobs yet. Tap 💾 Save under an alert."
    lines = ["<b>💾 Saved jobs</b> (latest 15)\n"]
    for r in rows:
        url = html.escape(r["url"] or "", quote=True)
        title = html.escape(r["title"])
        company = html.escape(r["company"])
        lines.append(f'• <a href="{url}">{title}</a> – {company} ({r["score"]})')
    return "\n".join(lines)


def format_stats(conn):
    c = db.status_counts(conn)
    alerts = c.get("notified", 0) + c.get("saved", 0) + c.get("skipped", 0)
    return (
        "<b>📊 Stats</b>\n"
        f"Scored in the last 7 days: {db.scored_since(conn, 7)}\n"
        f"Alerts sent in total: {alerts}\n"
        f"💾 Saved: {c.get('saved', 0)}\n"
        f"🚫 Skipped: {c.get('skipped', 0)}\n"
        f"⏳ Waiting to be sent: {c.get('pending', 0)}\n"
        f"Below threshold: {c.get('seen', 0)}\n"
        f"Filtered out before scoring: {c.get('filtered', 0)}"
    )


def handle_message(conn, msg):
    if str((msg.get("chat") or {}).get("id")).strip() != CHAT_ID:
        STATS["ignored_other_chat"] += 1
        return
    text = (msg.get("text") or "").strip().lower()
    cmd = text.split()[0].split("@")[0] if text else ""
    if cmd == "/saved":
        send_text(format_saved(conn))
        STATS["cmd_saved"] += 1
    elif cmd == "/stats":
        send_text(format_stats(conn))
        STATS["cmd_stats"] += 1
    elif cmd in ("/start", "/help"):
        send_text(HELP)
        STATS["cmd_help"] += 1
    else:
        STATS["ignored_text"] += 1


def handle_callback(conn, cq):
    msg = cq.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    if str(chat_id).strip() != CHAT_ID:
        STATS["ignored_other_chat"] += 1
        return
    action, _, job_id = (cq.get("data") or "").partition("|")
    job = db.get_job(conn, job_id)

    def answer(text):
        try:  # old button taps can no longer be answered; that is fine
            api("answerCallbackQuery", callback_query_id=cq["id"], text=text)
        except Exception:
            pass

    if not job or action not in ("s", "k", "u"):
        STATS["unknown_job"] += 1
        answer("Unknown job")
        return

    if action == "s":
        status, label, state = "saved", "Saved ✅", "saved"
    elif action == "k":
        status, label, state = "skipped", "Skipped 🚫", "skipped"
    else:
        status, label, state = "notified", "Restored", None

    db.mark(conn, job_id, status)
    STATS[f"tap_{status}"] += 1
    answer(label)
    api("editMessageReplyMarkup", chat_id=chat_id,
        message_id=msg["message_id"],
        reply_markup=job_keyboard(job, state))


def process_updates(conn, timeout=0):
    """Handle button taps and commands received since the last check."""
    offset = int(db.get_meta(conn, "tg_offset", "0"))
    data = api("getUpdates", offset=offset, timeout=timeout,
               allowed_updates=["message", "callback_query"])
    updates = data.get("result", [])
    for u in updates:
        try:
            if "callback_query" in u:
                handle_callback(conn, u["callback_query"])
            elif "message" in u:
                handle_message(conn, u["message"])
            else:
                STATS["other_update"] += 1
        except Exception as e:
            STATS["errors"] += 1
            print(f"Update failed: {type(e).__name__}: {e}", flush=True)
        db.set_meta(conn, "tg_offset", str(u["update_id"] + 1))
    if updates:
        print(f"Update outcomes: {dict(STATS)}", flush=True)
    return len(updates)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true",
                    help="keep listening (for an always-on machine)")
    args = ap.parse_args()
    conn = db.get_conn()

    if args.loop:
        print("Listening for Telegram updates...", flush=True)
        while True:
            try:
                process_updates(conn, timeout=50)
            except Exception as e:
                print(f"Error: {e}", flush=True)
                time.sleep(5)
    else:
        n = process_updates(conn)
        print(f"Processed {n} Telegram updates", flush=True)
        out = os.getenv("GITHUB_OUTPUT")
        if out and n:
            with open(out, "a") as f:
                f.write("changed=true\n")