"""CLI entry point for Company Curator.

SRP: Only responsible for parsing CLI arguments and wiring dependencies.
DIP: All components are created here and injected into the pipeline.
"""

import argparse
import sys

import anthropic

from company_curator.config import load_config
from company_curator.data.db import Database
from company_curator.data.fetcher import YFinanceDataFetcher
from company_curator.notifications.emailer import EmailNotifier
from company_curator.scheduler import DailyPipeline
from company_curator.watchlist.manager import WatchlistManager


def _build_dependencies():
    """Wire up all dependencies (composition root)."""
    config = load_config()

    if not config.api.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    db = Database(config.db_path)
    db.connect()

    client = anthropic.Anthropic(api_key=config.api.anthropic_api_key)
    fetcher = YFinanceDataFetcher()
    notifier = EmailNotifier(config.email)

    return config, db, client, fetcher, notifier


def cmd_discover(args: argparse.Namespace) -> None:
    """Run the daily discovery pipeline."""
    config, db, client, fetcher, notifier = _build_dependencies()
    pipeline = DailyPipeline(config, db, fetcher, client, notifier)
    report = pipeline.run()
    print("\n" + report)
    db.close()


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze a specific ticker."""
    config, db, client, fetcher, notifier = _build_dependencies()

    from company_curator.analysis.deep_dive import DeepDiveAnalyzer
    from company_curator.analysis.peer_comparison import PeerComparisonAnalyzer
    from company_curator.analysis.short_report import ShortReportAnalyzer

    ticker = args.ticker.upper()
    info = fetcher.get_company_info(ticker)
    if not info:
        print(f"Error: Could not find company data for {ticker}")
        return

    print(f"\nAnalyzing {ticker} ({info.name})...\n")

    deep_dive = DeepDiveAnalyzer(client, fetcher)
    print("## Deep Dive\n")
    print(deep_dive.analyze(ticker))

    if args.competitors:
        comps = [c.strip().upper() for c in args.competitors.split(",")]
        if len(comps) >= 2:
            peer_comp = PeerComparisonAnalyzer(client, fetcher)
            print("\n## Peer Comparison\n")
            print(peer_comp.analyze(ticker, comps[0], comps[1]))

    short = ShortReportAnalyzer(client, fetcher)
    print("\n## Short Report (Risk Assessment)\n")
    print(short.analyze(ticker))

    db.close()


def cmd_watchlist_add(args: argparse.Namespace) -> None:
    """Add a ticker to the watchlist."""
    config, db, client, fetcher, notifier = _build_dependencies()
    manager = WatchlistManager(db)

    ticker = args.ticker.upper()
    if manager.exists(ticker):
        print(f"{ticker} is already on the watchlist.")
        db.close()
        return

    info = fetcher.get_company_info(ticker)
    if not info:
        print(f"Error: Could not find company data for {ticker}")
        db.close()
        return

    metrics = fetcher.get_financial_metrics(ticker)
    entry_revenue = metrics.revenue_ttm if metrics else None

    entry = manager.add(
        ticker=ticker,
        company_name=info.name,
        entry_price=info.current_price,
        entry_revenue=entry_revenue,
        notes=args.notes,
    )
    print(f"Added {entry.ticker} ({entry.company_name}) to watchlist at ${entry.entry_price:.2f}")
    db.close()


def cmd_watchlist_remove(args: argparse.Namespace) -> None:
    """Remove a ticker from the watchlist."""
    config, db, client, fetcher, notifier = _build_dependencies()
    manager = WatchlistManager(db)

    ticker = args.ticker.upper()
    if manager.remove(ticker):
        print(f"Removed {ticker} from watchlist.")
    else:
        print(f"{ticker} is not on the active watchlist.")
    db.close()


def cmd_watchlist_list(args: argparse.Namespace) -> None:
    """List all watchlist entries."""
    config, db, client, fetcher, notifier = _build_dependencies()
    manager = WatchlistManager(db)

    entries = manager.list_active()
    if not entries:
        print("Watchlist is empty.")
    else:
        print(f"\n{'Ticker':<8} {'Company':<30} {'Entry Price':<12} {'Added':<12}")
        print("-" * 65)
        for e in entries:
            date = e.added_date[:10]
            print(f"{e.ticker:<8} {e.company_name:<30} ${e.entry_price:<11.2f} {date:<12}")
    db.close()


def cmd_status(args: argparse.Namespace) -> None:
    """Show watchlist status and pending alerts."""
    config, db, client, fetcher, notifier = _build_dependencies()
    manager = WatchlistManager(db)

    from company_curator.watchlist.alerts import AlertManager
    from company_curator.watchlist.monitor import GrowthMonitor

    monitor = GrowthMonitor(
        db, fetcher,
        price_threshold_pct=config.watchlist.min_price_growth_pct,
        revenue_threshold_pct=config.watchlist.min_revenue_growth_pct,
        monitoring_days=config.watchlist.monitoring_period_days,
    )
    alert_mgr = AlertManager(db)

    entries = manager.list_active()
    if not entries:
        print("Watchlist is empty.")
    else:
        print("\n## Watchlist Growth Status\n")
        for entry in entries:
            report = monitor.evaluate(entry)
            status = "INVESTMENT READY" if report.ready_for_investment else f"Day {report.days_watched}/90"
            print(
                f"  {report.ticker:<8} ${report.current_price:>8.2f}  "
                f"{report.price_change_pct:>+6.1f}%  {status}"
            )

    alerts = alert_mgr.get_unacknowledged()
    if alerts:
        print("\n## Pending Alerts\n")
        for alert in alerts:
            print(f"  [{alert.id}] {alert.message}")

    db.close()


def cmd_schedule(args: argparse.Namespace) -> None:
    """Set up the daily cron job."""
    import os
    script_path = os.path.abspath(__file__)
    python_path = sys.executable
    cron_line = f"0 7 * * 1-5 cd {os.path.dirname(os.path.dirname(script_path))} && {python_path} -m company_curator discover"

    print("Add this line to your crontab (crontab -e):\n")
    print(f"  {cron_line}\n")
    print("This runs the discovery pipeline at 7:00 AM on weekdays.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="company_curator",
        description="Autonomous investment research curator",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # discover
    subparsers.add_parser("discover", help="Run daily discovery pipeline")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a specific ticker")
    analyze_parser.add_argument("ticker", help="Stock ticker symbol")
    analyze_parser.add_argument("--competitors", "-c", help="Comma-separated competitor tickers")

    # watchlist
    watchlist_parser = subparsers.add_parser("watchlist", help="Manage watchlist")
    watchlist_sub = watchlist_parser.add_subparsers(dest="watchlist_command")

    add_parser = watchlist_sub.add_parser("add", help="Add ticker to watchlist")
    add_parser.add_argument("ticker", help="Stock ticker symbol")
    add_parser.add_argument("--notes", "-n", help="Optional notes")

    remove_parser = watchlist_sub.add_parser("remove", help="Remove ticker from watchlist")
    remove_parser.add_argument("ticker", help="Stock ticker symbol")

    watchlist_sub.add_parser("list", help="List watchlist entries")

    # status
    subparsers.add_parser("status", help="Show watchlist status and alerts")

    # schedule
    subparsers.add_parser("schedule", help="Show cron setup instructions")

    args = parser.parse_args()

    commands = {
        "discover": cmd_discover,
        "analyze": cmd_analyze,
        "status": cmd_status,
        "schedule": cmd_schedule,
    }

    if args.command == "watchlist":
        watchlist_commands = {
            "add": cmd_watchlist_add,
            "remove": cmd_watchlist_remove,
            "list": cmd_watchlist_list,
        }
        handler = watchlist_commands.get(args.watchlist_command)
        if handler:
            handler(args)
        else:
            watchlist_parser.print_help()
    elif args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
