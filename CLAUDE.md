# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow (MANDATORY — follow every time before coding)

1. **Plan First** — Before writing any code, produce a written plan broken into a to-do checklist of discrete steps. Track progress against it as you work.
2. **SOLID** — Design/review against SOLID principles (below) before writing any code.
3. **Code** — Implement following the design.
4. **GitHub/Document** — Commit with clear messages (conventional commits), push, update docs.

Park future ideas and not-yet-scoped features in `IDEAS.md` rather than building them immediately.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt      # includes runtime deps + pytest/ruff
cp .env.example .env                      # then fill in ANTHROPIC_API_KEY, SMTP, etc.

# Web app (dev)
python -m company_curator serve --debug   # http://0.0.0.0:5050

# CLI pipelines (operate on DEFAULT_USER_ID=1)
python -m company_curator discover        # run the daily discovery pipeline once
python -m company_curator analyze NVDA -c AMD,INTC   # ad-hoc single-ticker analysis
python -m company_curator audit           # run the monthly watchlist audit
python -m company_curator status          # watchlist growth status + pending alerts
python -m company_curator watchlist add|remove|list NVDA
python -m company_curator schedule        # install a macOS launchd daily job (dev only)

# Tests & lint (CI runs both on Python 3.11)
pytest tests/ -v
pytest tests/test_watchlist.py::test_name    # single test
ruff check company_curator/ tests/
```

Note: CI targets Python 3.11 (ruff `target-version = py311`); local dev may run 3.9. Type hints are required on all function signatures. `ruff.toml` sets line-length 120 and ignores E501.

## Architecture (big picture)

Company Curator is a **multi-user** investment-research tool with three entry points that share the same domain layer:

- **`wsgi.py`** → production composition root. Builds the Flask app and, when `RUN_SCHEDULER=1`, starts the in-process APScheduler. This is what gunicorn/Fly runs.
- **`company_curator/main.py`** → CLI composition root. Wires dependencies and runs pipelines for `DEFAULT_USER_ID=1` only.
- **`company_curator/web/app.py`** → `create_app()` application factory.

**Dependency injection is the core pattern.** Nothing constructs its own DB/API-client/emailer; the composition roots build `Config`, `Database`, `anthropic.Anthropic`, `YFinanceDataFetcher`, and `EmailNotifier`, then inject them down through the pipelines and Flask blueprints (dependencies are stashed in `app.config["APP_*"]` for routes). When adding a feature, follow the existing chain rather than importing concretions or reading `os.environ` directly — config loading lives only in `config.py`.

**Orchestration lives in `scheduler.py`:** `DailyPipeline` (discovery → per-pick deep analysis → watchlist monitoring → email + save report) and `MonthlyAuditPipeline`. These are the heart of the app; most modules exist to serve one pipeline step. Both are deliberately fault-tolerant — each step is wrapped so one failure degrades that section instead of killing the run and the email still sends.

**Domain flow (one daily run):**
`discovery/screener.py` (GrowthScreener finds candidates via yfinance) → `discovery/scorer.py` (QualitativeScorer ranks with Claude, honoring per-user `discovery/preferences.py`) → `analysis/{deep_dive,peer_comparison,short_report,movement_notes}.py` (Claude-powered reports) → `watchlist/{monitor,price_tracker,alerts}.py` → `notifications/emailer.py`.

**Swappable components use ABCs** (Open/Closed): `BaseDataFetcher` (`data/fetcher.py`), `BaseNotifier` (`notifications/emailer.py`). New data sources or notification channels (Slack, SMS) should subclass these, not modify callers. All implementations must honor the base contract (Liskov).

**Scheduling:** in production, `scheduler_service.py` runs one APScheduler cron job (9:00 AM Pacific, Mon–Fri) that iterates every user with a 5-minute stagger. `WEB_CONCURRENCY=1` is mandatory — multiple gunicorn workers would each start the scheduler and send duplicate emails. The `schedule` CLI command is a separate macOS-only launchd path for local dev.

### Data layer (important, non-obvious)

- `data/db.py` `Database` wraps a SQLAlchemy engine with **thread-local scoped sessions**. It exposes both the ORM (`db.session`) and a **raw-SQL compatibility layer** (`db.execute/fetchone/fetchall/commit`) that accepts `?` placeholders and converts them to named params. Both styles are in active use — pipelines lean on raw SQL, routes lean on the ORM. This is intentional (gradual migration), not a mistake to "fix."
- **Schema is created at runtime** by `Base.metadata.create_all()` in `Database.connect()`. Alembic is scaffolded (`alembic.ini`, `migrations/`) but `migrations/versions/` is currently empty — there are no migrations yet, and new columns are added via ORM model changes (see the `server_default` / additive-column pattern in `data/models.py`).
- Every domain table is **scoped by `user_id`** with a uniqueness constraint. Managers (`WatchlistManager`, `AlertManager`, etc.) take a `user_id` in their constructor; never write cross-user queries.
- Per-user SMTP passwords are Fernet-encrypted at rest (`utils/crypto.py`, `FERNET_KEY`); `EmailNotifier.build_from_user` decrypts them, falling back to the global SMTP account in `EmailConfig`.

### Web layer

Flask blueprints in `web/routes/` (`auth`, `dashboard`, `watchlist`, `reports`, `audit`, `preferences`, `ai_chat`), registered in `create_app` with url-prefixes. Auth is flask-login + bcrypt; CSRF via flask-wtf (the `ai_chat` AJAX blueprint is CSRF-exempt and uses a custom header); rate limiting via flask-limiter keyed on the real client IP (`Fly-Client-IP` header behind Fly's proxy). `DEV_AUTO_LOGIN=1` auto-logs-in user 1 for local dev — never set in production. Report markdown is rendered to HTML by the hand-rolled `_md_to_html` Jinja filter in `web/app.py`.

### Deployment

Deployed to **Fly.io** (`fly.toml`): SQLite on a persistent volume at `/data`, machine kept always-on so the scheduler fires, `RUN_SCHEDULER=1`. Deploys are **manual** — run `fly deploy` from your machine. CI (`.github/workflows/ci.yml`) only runs lint + tests; it does not deploy.

## SOLID Principles (design against these before coding)

- **SRP** — One reason to change per module. Screener screens, Scorer scores, Fetcher fetches, Emailer emails. If a module does two things, split it.
- **OCP** — Add new screener strategies, scoring models, data sources, or notification channels by extending the ABCs, without modifying existing code.
- **LSP** — Every `BaseDataFetcher` / `BaseNotifier` subclass must be substitutable for its base.
- **ISP** — Small, focused interfaces; no class depends on methods it doesn't use.
- **DIP** — Depend on abstractions; inject DB, API clients, and emailer rather than hardcoding.

## Commit Messages

Conventional commits: `type(scope): description` — types `feat|fix|refactor|docs|test|chore`. Example: `feat(discovery): add momentum-based screener`.

## Key Design Decisions

- **3 picks per day** (per-user configurable 1–5 via preferences) — screener finds candidates, scorer ranks, top N presented.
- **All sectors** — no hard sector filtering; users narrow via preferences. Focus on high-growth potential.
- **Qualitative emphasis** — sentiment, culture, and moat matter as much as the numbers.
- **3-month (90-day) watchlist window** — an investment alert requires BOTH price appreciation (≥15%) AND revenue growth (≥10%).
- **Email is the primary notification channel**; the web app is the interaction surface.
- **Per-user preferences** drive discovery thresholds; unset numeric thresholds are derived from the user's risk profile (`discovery/preferences.py`).
