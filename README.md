# Company Curator

An autonomous investment research tool that discovers high-growth companies, analyzes them, and tracks them through a watchlist pipeline.

## What It Does

1. **Daily Discovery** — Scans the market for high-growth candidates across all sectors, scoring them on qualitative factors (sentiment, culture, moat, catalysts)
2. **Deep Analysis** — Runs 3 research reports on each pick:
   - **The Deep Dive** — Business model, moat & competition, catalysts, asymmetry check
   - **Peer Comparison Table** — Relative valuation vs competitors (P/S, EV/EBITDA, gross margin, YoY revenue growth)
   - **The Short Report** — Skeptic risk assessment (accounting, customer concentration, competitive threats)
3. **Watchlist** — Add companies you like, track them over time
4. **3-Month Growth Monitor** — After 3 months of sustained growth (price + revenue), you get an investment reminder

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/Company_Curator.git
cd Company_Curator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and email settings
```

## Configuration

Set these in your `.env` file:

```
ANTHROPIC_API_KEY=your-api-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=your-email@gmail.com
```

## Usage

```bash
# Run daily discovery (finds top 3 picks)
python -m company_curator discover

# Analyze a specific ticker
python -m company_curator analyze NVDA

# Watchlist management
python -m company_curator watchlist add NVDA
python -m company_curator watchlist remove NVDA
python -m company_curator watchlist list

# Check watchlist status and alerts
python -m company_curator status

# Set up daily cron job
python -m company_curator schedule
```

## Architecture

Built with SOLID principles. See [CLAUDE.md](CLAUDE.md) for full development guide.

## License

MIT
