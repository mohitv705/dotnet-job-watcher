# dotnet-job-watcher

Checks a list of target companies' job boards daily for postings matching
`.NET`, `C#`, `ASP.NET Core`, `backend`, etc. (plus optional location /
remote / experience-level filters), and notifies you (Telegram and/or
email, with retry-on-failure) about postings that are *new* since the
last run.

## Project layout

```
check_jobs.py              orchestrates: fetch (concurrently) -> filter -> diff -> notify
keywords.py                 the base .NET/C#/backend keyword regex
filters.py                  location / remote / include-exclude / experience filtering
retry.py                    shared exponential-backoff retry decorator
config/companies.yaml       your target company list + filter settings
state.json                  auto-created; tracks what's already been seen

providers/                  one module per job-board platform
  base.py                     shared Job dataclass
  http.py                     shared requests session + retry wrapper
  greenhouse.py, lever.py, workday.py, smartrecruiters.py, ashby.py
  icims.py, successfactors.py   best-effort (see caveats below)
  generic.py                   HTML/keyword-link fallback for anything else

notifications/              one module per notification channel
  telegram.py                 rich per-job cards, auto-chunked for long batches
  email.py                    plain-text summary over SMTP
  __init__.py                  fans out to every configured channel

.github/workflows/job-check.yml   daily scheduled run via GitHub Actions
```

## Supported job-board platforms

| type              | value in companies.yaml                          | reliability |
|-------------------|---------------------------------------------------|-------------|
| `greenhouse`      | board token (`boards.greenhouse.io/<TOKEN>`)       | High — public JSON API |
| `lever`           | company slug (`jobs.lever.co/<SLUG>`)              | High — public JSON API |
| `workday`         | `{tenant, wd_host, site}` mapping                  | High — public JSON API |
| `smartrecruiters` | company identifier                                 | High — public JSON API |
| `ashby`           | job board name (`jobs.ashbyhq.com/<NAME>`)         | High — public JSON API |
| `icims`           | careers/search page URL                            | **Best-effort** — no standard public API, often JS-rendered |
| `successfactors`  | careers/search page URL                            | **Best-effort** — same caveat as iCIMS |
| `generic`         | careers page URL                                   | Best-effort — plain HTML only, no JS rendering |

For `icims` and `successfactors`, there's no consistent public API across
tenants the way there is for the others — if a company on either platform
returns zero matches and you know they have open roles, open that page's
browser devtools → Network tab, find the JSON request the page itself
makes, and either point `generic` at that JSON URL or adapt
`providers/icims.py` / `providers/successfactors.py` once you've confirmed
the pattern.

To find which platform a company uses: open a job posting and check the
URL, or view-source on the careers page and search for the platform name.

## Filters

Set filters globally in `companies.yaml` under the top-level `filters:`
key, or per-company (which fully replaces the global filter for that
company):

```yaml
filters:
  remote_only: true
  locations: ["Kolkata", "India"]      # any-of match against location text
  keywords_include: ["Azure"]          # ALL must appear in title/description
  keywords_exclude: ["Senior", "Lead"] # dropped if ANY appear
  experience_levels: ["junior", "0-2 years"]  # any-of match
```

Every field is optional — omit or leave empty to skip that filter.

## Setup

### 1. Fill in your target companies

Edit `config/companies.yaml` — see the table above for what `value` should
be for each platform. Aim for 30–50 companies, mixing platforms as needed.

### 2. Set up a notification channel

**Telegram (recommended — 2 minutes):**
1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts — you'll get a bot token.
2. Message your new bot anything, then visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` — your chat ID is in the JSON under `message.chat.id`.

**Email (alternative, or in addition):** SMTP credentials — e.g. a Gmail
account with an [app password](https://support.google.com/accounts/answer/185833).

Both can be configured at once — you'll get notified on whichever (or both) are set up.

### 3. Push this to a GitHub repo

```bash
cd dotnet-job-watcher
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 4. Add secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**

Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL_TO`

### 5. Test it

**Actions** tab → "Check .NET job postings" → **Run workflow**. Everything
will look "new" on the first run (expected, since there's no prior state).

## Running locally

```bash
pip install -r requirements.txt
python check_jobs.py
```

## Notes on the concurrent fetch

Companies are fetched in parallel (up to 10 at a time) using a thread
pool, since these are I/O-bound network calls. A failure fetching one
company (timeout, bad config, site down) is logged and skipped — it
won't stop the rest of the run, and that company's prior state is kept
so nothing gets falsely reported as "new" once the site recovers.

## Notes on retries

Every HTTP call (in providers and in the notifiers) retries up to 3
times with exponential backoff (plus jitter) on transient network
errors before giving up — handles rate limits, brief outages, flaky
DNS, etc. without failing the whole run over a one-off blip.
