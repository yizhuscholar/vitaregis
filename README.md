# Vitaregis: healthcare, AI and business briefing

A static site (GitHub Pages) refreshed daily by a GitHub Action.

## One-time setup
1. Create a new GitHub repo (e.g. `Vitaregis`) and upload everything in this folder, keeping the `.github` folder.
2. Repo **Settings > Pages > Source: GitHub Actions**.
3. (Optional) **Settings > Secrets and variables > Actions**: add `CONTACT_EMAIL` (polite Crossref access) and, for live job listings, `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` (free at developer.adzuna.com).
4. **Actions tab > Update and deploy Vitaregis > Run workflow**. Your site appears at `https://<username>.github.io/<repo>/`.

## What updates automatically
- `data/news.json`: RSS feeds in `scripts/update.py` (FEEDS), last 7 days, tagged AI / business / policy.
- `data/papers.json`: Crossref, last 5 years, UTD 24 / FT 50 journals listed in JOURNALS.
- `data/jobs.json`: Adzuna, last 7 days (needs the two secrets).

## What you edit by hand
- `data/conferences.json`: add or fix conferences.
- `FEEDS`, `JOURNALS`, `JOB_QUERIES` in `scripts/update.py`.

If a source fails, the script keeps the previous data for it.
