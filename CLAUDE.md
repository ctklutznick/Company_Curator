# Company Curator - Development Guide

## Workflow (MANDATORY — follow every time before coding)

1. **SOLID First** — Design/review against SOLID principles before writing any code
2. **Code** — Implement following the design
3. **GitHub/Document** — Commit with clear messages, push, update docs

## SOLID Principles

### Single Responsibility Principle (SRP)
- Each class/module has ONE reason to change
- Screener screens. Scorer scores. Fetcher fetches. Emailer emails.
- If a module does two things, split it.

### Open/Closed Principle (OCP)
- Open for extension, closed for modification
- Use abstract base classes and interfaces for swappable components
- New screener strategies, scoring models, or notification channels should be addable without modifying existing code

### Liskov Substitution Principle (LSP)
- Subclasses must be substitutable for their base classes
- All data source implementations must honor the same contract

### Interface Segregation Principle (ISP)
- No class should depend on methods it doesn't use
- Keep interfaces small and focused

### Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- Inject dependencies (DB, API clients, emailer) rather than hardcoding them

## Project Architecture

```
company_curator/
├── main.py                # CLI entry point
├── config.py              # Settings, thresholds, API keys
├── discovery/
│   ├── screener.py        # Market screening (finds candidates)
│   └── scorer.py          # Claude-powered qualitative ranking
├── analysis/
│   ├── prompts.py         # 3 prompt templates (Deep Dive, Peer Comparison, Short Report)
│   ├── deep_dive.py       # Business model, moat, catalysts, asymmetry
│   ├── peer_comparison.py # Relative valuation table
│   └── short_report.py    # Skeptic risk assessment
├── watchlist/
│   ├── manager.py         # Add/remove/list watchlist entries
│   ├── monitor.py         # Track growth over 3 months
│   └── alerts.py          # Investment reminders
├── data/
│   ├── fetcher.py         # yfinance / market data
│   └── db.py              # SQLite persistence
├── notifications/
│   └── emailer.py         # Daily email reports
└── scheduler.py           # Daily cron job
```

## Coding Standards

- Python 3.11+
- Type hints on all function signatures
- Abstract base classes for swappable components
- Dependency injection over global state
- SQLite for local persistence
- No hardcoded API keys — use environment variables or .env
- Keep functions short and focused (<30 lines where possible)

## Commit Messages

- Use conventional commit format: `type(scope): description`
- Types: feat, fix, refactor, docs, test, chore
- Example: `feat(discovery): add momentum-based screener`

## Key Design Decisions

- **3 picks per day** — screener finds candidates, scorer ranks, top 3 presented
- **All sectors** — no sector filtering, focus on high-growth potential
- **Qualitative emphasis** — sentiment, culture, moat matter as much as numbers
- **3-month watchlist window** — both price appreciation AND revenue growth required
- **Daily email** — primary notification channel
