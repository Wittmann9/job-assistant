# Job Assistant

[![Job assistant](https://github.com/Wittmann9/job-assistant/actions/workflows/job-assistant.yml/badge.svg)](https://github.com/Wittmann9/job-assistant/actions/workflows/job-assistant.yml)

A personalised job search assistant. It pulls new listings from the German Federal Employment Agency (Bundesagentur für Arbeit), filters them, lets an LLM score each one against my own profile, and sends the best matches to me on Telegram, with buttons to save or skip each job. It runs on a schedule with GitHub Actions, so no server is needed.

![Telegram alert](docs/telegram-alert.png)

## Features

- **Personalised scoring.** Every job is scored from 0 to 100 against a free-text profile and comes with a two-sentence reason, so I can see why it matched.
- **Cost-aware pipeline.** Cheap rule-based filters run first, and the LLM only sees plausible jobs.
- **Deduplication.** Jobs already seen are never scored or sent twice, even when the same job is posted more than once.
- **Telegram alerts with buttons.** Each alert has Save, Skip and Open listing buttons, and a tap on Save or Skip can be undone.
- **Commands.** `/saved` lists saved jobs and `/stats` summarises what was found, scored, saved and skipped.
- **Runs without a server.** Scheduled GitHub Actions workflows, with state kept in the Actions cache.
- **Private by design.** Credentials and the personal profile live in secrets, and workflow logs never contain job titles or scores.

## Why I built it

Job boards return hundreds of loosely related listings, and the ones that matter are easy to miss. I wanted an assistant that knows what I am looking for (roles, location, on-site preference, what should score low), reads the full job text, explains its score, and only interrupts me when a match is strong.

## How it works

```mermaid
flowchart LR
    A[Bundesagentur<br/>job search API] --> B[Normalize and<br/>deduplicate]
    B --> C[Title filter]
    C --> D[Fetch full<br/>description]
    D --> E[Keyword filter]
    E --> F[LLM scoring<br/>0-100 + reason]
    F --> G{Score above<br/>threshold?}
    G -- yes --> H[Telegram alert<br/>Save / Skip / Open]
    G -- no --> I[(SQLite)]
    H --> I
    H -. button taps and<br/>commands .-> J[Telegram sync]
    J --> I
```

1. **Fetch:** one search per target job title and location, limited to recently published jobs.
2. **Deduplicate:** jobs already stored in SQLite are skipped, matched by ID and by company + title + location.
3. **Cheap filters first:** excluded words in the title drop a job immediately. Only then is the full description loaded, and a whole-word keyword check removes unrelated jobs.
4. **LLM scoring:** the remaining jobs are scored against the profile and return structured JSON (score, short reason, matched skills, red flags).
5. **Notify:** jobs above the threshold are queued and sent best first, with a cap per run so a first run or a backlog cannot flood the chat.
6. **Feedback:** taps on Save and Skip, and the commands, are collected from Telegram and written to the same database.

## Telegram interaction

| Control | What it does |
|---|---|
| 💾 Save | marks the job as saved and turns the buttons into an Undo button |
| 🚫 Skip | marks the job as skipped, with Undo |
| 🔗 Open listing | opens the posting directly |
| `/saved` | shows the latest 15 saved jobs as links |
| `/stats` | shows counts: scored, alerts sent, saved, skipped, waiting, below threshold, filtered |
| `/help` | lists the commands |

**How taps are processed.** Telegram keeps a tap until a program asks for it, and a scheduled GitHub Actions job is not running all the time. So taps are recorded the next time the bot checks Telegram:

| Setup | Delay before a tap is recorded |
|---|---|
| Start of every main run | up to a few hours |
| Plus the `telegram-sync` workflow | about 10 minutes (GitHub can delay scheduled runs) |
| `python bot.py --loop` on an always-on machine | instant |

The bot only obeys the chat ID configured in the secrets, so strangers who find the bot get no response.

## Tech stack

- Python 3.12
- Bundesagentur job search service (public endpoint, no account needed)
- OpenAI API for scoring (the model is one constant in `scoring.py`)
- Telegram Bot API for notifications, buttons and commands
- SQLite for state
- GitHub Actions for scheduling, with the database persisted between runs via the Actions cache

## Project structure

```
job-assistant/
├── main.py                  # pipeline and command line options
├── sources.py               # Bundesagentur search and job details
├── filters.py               # title and keyword filters
├── scoring.py               # LLM scoring
├── db.py                    # SQLite storage, deduplication, stats queries
├── notify.py                # Telegram messages and buttons
├── bot.py                   # button taps and commands
├── profile.example.yaml     # example configuration
├── requirements.txt
└── .github/workflows/
    ├── job-assistant.yml    # scheduled search, scoring and alerts
    └── telegram-sync.yml    # frequent check for taps and commands
```

## Run it locally

```bash
git clone https://github.com/Wittmann9/job-assistant.git
cd job-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your own credentials:

```
OPENAI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

To get the Telegram values, create a bot with `@BotFather`, send your bot a message, and read your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`.

Create your profile from the example and edit it:

```bash
cp profile.example.yaml profile.yaml
```

Try it without sending anything:

```bash
python main.py --days 7 --limit 20 --dry-run
```

Then run it for real:

```bash
python main.py --days 7 --limit 20 --max-alerts 5
```

| Option | Meaning |
|---|---|
| `--days N` | only jobs published in the last N days |
| `--limit N` | score at most N new jobs per run |
| `--max-alerts N` | send at most N Telegram messages per run |
| `--dry-run` | score and store jobs, but send no messages and skip the Telegram check |

To process button taps and commands by hand, run `python bot.py`. For an always-on machine, `python bot.py --loop` keeps listening.

**Use a separate bot for local testing.** Every process that polls Telegram takes taps away from the others, so a local test with the production bot token would swallow taps meant for the scheduled workflows. Create a second bot with `@BotFather` for development.

## Configuration

Everything personal lives in `profile.yaml`, so behaviour can be tuned without touching code.

| Key | Purpose |
|---|---|
| `target_roles` | job titles and keywords searched on the Bundesagentur (German and English) |
| `locations` | cities to search, with a 50 km radius |
| `relevance_keywords` | a job must mention at least one of these, as a whole word, to be scored |
| `exclude_keywords` | jobs with these words in the title are dropped immediately |
| `min_score_to_notify` | minimum LLM score (0-100) for an alert |
| `about_me` | free text the scorer reads: background, wanted roles, location, what should score low |
| `must_have_keywords`, `nice_to_have` | skills passed to the scorer as context |

`about_me` has the biggest effect on result quality. Being specific about what should score *low* helps as much as describing what should score high.

## Run it on a schedule (GitHub Actions)

Two workflows share one concurrency group, so they never touch the database at the same time:

- `job-assistant.yml` runs several times a day. It records pending taps, searches, scores and sends alerts. It can also be started by hand, with an optional dry-run switch.
- `telegram-sync.yml` runs every few minutes and only handles button taps and commands. It is optional.

Setup:

1. Fork or clone the repository into your own account.
2. Under **Settings → Secrets and variables → Actions**, add these secrets:

   | Secret | Value |
   |---|---|
   | `OPENAI_API_KEY` | your OpenAI key |
   | `TELEGRAM_BOT_TOKEN` | your bot token |
   | `TELEGRAM_CHAT_ID` | your chat ID |
   | `PROFILE_YAML` | the full contents of your `profile.yaml` |

3. Open the **Actions** tab and run the main workflow once with dry run enabled to check the setup, then once without it.

Notes:

- The SQLite database is saved to the Actions cache after each run and restored at the start of the next one.
- The workflow sets `QUIET=1`, so job titles and scores never appear in logs. This matters because logs of public repositories are visible to everyone.
- Logs show only counts, such as how many jobs were found and how many Telegram updates were processed.
- Scheduled workflows in public repositories are paused after a period without repository activity. GitHub sends a warning, and any commit resets it.

## Design decisions

- **Cheap filters before the LLM.** Rules run first and the model only sees plausible jobs, which keeps cost low and the model focused.
- **Deduplication on two keys.** The ID catches repeats, and company + title + location catches the same job posted twice.
- **Failures are retried, not stored.** If loading a description or scoring fails, the job is not saved and is picked up again on the next run.
- **Flood protection.** A cap on jobs scored per run and on alerts sent per run keeps the first run, and any backlog, manageable. Waiting alerts are sent best first.
- **Polling instead of a webhook.** A scheduled workflow cannot host a webhook, so button taps are collected with Telegram's update queue and an offset stored in the database. Each update is handled once.
- **One consumer for the update queue.** Only the scheduled workflows poll the production bot. Local testing uses a separate bot.
- **Personal data stays out of the repository.** Credentials come from environment variables or secrets, the real profile is injected from a secret, and the repository only contains an example profile.
- **No scraping of job boards that forbid it.** Sources with a public interface are preferred. StepStone is deliberately not scraped, because of its terms of use and bot protection. Parsing job alert emails would be the cleaner way to add it.

## Limitations

- The Bundesagentur search service has no official documentation, so field names or paths can change and the code may need adjusting. It is a public endpoint used by the agency's own website.
- Only one source is implemented so far.
- Button taps are not instant unless the bot runs on an always-on machine. GitHub also delays scheduled runs, sometimes by several minutes.
- Score quality depends on the profile text, and the model can be wrong. Treat scores as a ranking aid and read the posting before deciding.
- The first run after a cache loss treats old jobs as new, which the alert cap limits.
- There are no automated tests yet.

## Cost

Cost depends on the model and on how many jobs pass the filters. With a small model it is typically a few cents per day. Check your provider's usage page after the first day, and keep automatic recharge off while testing.

## Roadmap

- Use Save and Skip feedback to improve scoring, for example by adding examples of liked and disliked jobs to the prompt
- Unit tests for the filters and the database
- More sources, such as company career feeds and job alert emails
- Weekly summary message

## Disclaimer

This is a personal project. It is not affiliated with or endorsed by the Bundesagentur für Arbeit, OpenAI, or Telegram. Respect each service's terms of use and keep request volumes low.

## Author

[Your name] · [LinkedIn or website]

## License

MIT, see [LICENSE](LICENSE).
