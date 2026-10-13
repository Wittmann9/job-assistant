import argparse
import os
import time

import yaml
from dotenv import load_dotenv

import db
from bot import process_updates
from filters import title_ok, description_ok
from notify import send_job
from scoring import score_job
from sources import search_arbeitsagentur, fetch_description

load_dotenv()

# In QUIET mode (GitHub Actions) job titles and scores are never printed,
# because logs of public repositories are visible to everyone.
QUIET = os.getenv("QUIET") == "1"


def load_profile():
    with open("profile.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_profile_text(p):
    text = p["about_me"]
    text += "\nTarget roles: " + ", ".join(p["target_roles"])
    skills = p.get("must_have_keywords", []) + p.get("nice_to_have", [])
    text += "\nSkills: " + ", ".join(skills)
    text += "\nLanguages: " + ", ".join(p.get("languages", []))
    return text


def collect(profile, days):
    found = {}
    for role in profile["target_roles"]:
        for loc in profile["locations"]:
            for j in search_arbeitsagentur(role, location=loc, days=days):
                found[j["id"]] = j
    return list(found.values())


def run_cycle(days, dry_run, max_alerts, limit):
    profile = load_profile()
    profile_text = build_profile_text(profile)
    threshold = profile.get("min_score_to_notify", 70)
    conn = db.get_conn()

    # Record button taps and commands received since the last run
    if not dry_run:
        try:
            n = process_updates(conn)
            print(f"Processed {n} Telegram updates", flush=True)
        except Exception as e:
            print(f"Telegram update check failed: {e}", flush=True)

    jobs = collect(profile, days)
    new = [j for j in jobs if not db.exists(conn, j)]
    print(f"Found {len(jobs)} jobs, {len(new)} new", flush=True)
    if limit:
        new = new[:limit]
        print(f"Processing only the first {len(new)} (--limit)", flush=True)

    for i, j in enumerate(new, 1):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(new)}", flush=True)

        if not title_ok(j, profile):
            db.save(conn, j, 0, "excluded by title", "filtered")
            continue

        try:
            j["description"] = fetch_description(j["refnr"])
        except Exception as e:
            if not QUIET:
                print(f"  could not load description for {j['title']}: {e}")
            continue  # not saved, so it is retried next run
        time.sleep(0.5)

        if not description_ok(j, profile):
            db.save(conn, j, 0, "no relevant keywords", "filtered")
            continue

        result = score_job(j, profile_text)
        if result.get("reason") == "scoring failed":
            continue  # not saved, so it is retried next run
        try:
            score = int(result.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        status = "pending" if score >= threshold else "seen"
        db.save(conn, j, score, result.get("reason", ""), status)
        if not QUIET:
            print(f"  {score:3d}  {j['title'][:60]} | {j['company'][:25]}")

    to_send = db.pending(conn, max_alerts)
    print(f"Alerts to send: {len(to_send)}", flush=True)
    for j in to_send:
        if dry_run:
            if not QUIET:
                print(f"  [dry run] {j['score']}  {j['title']} | {j['company']}")
        else:
            send_job(j)
            db.mark(conn, j["id"], "notified")
            time.sleep(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7,
                    help="only jobs published in the last N days")
    ap.add_argument("--max-alerts", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0,
                    help="process at most N new jobs (for testing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="score and store jobs but do not send to Telegram")
    a = ap.parse_args()
    run_cycle(a.days, a.dry_run, a.max_alerts, a.limit)