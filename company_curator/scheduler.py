"""Daily scheduler for automated discovery and monitoring.

SRP: Only responsible for orchestrating the daily pipeline.
DIP: All dependencies are injected via the constructor.
"""

from __future__ import annotations

from datetime import datetime

import anthropic

from company_curator.analysis.deep_dive import DeepDiveAnalyzer
from company_curator.analysis.peer_comparison import PeerComparisonAnalyzer
from company_curator.analysis.short_report import ShortReportAnalyzer
from company_curator.config import Config
from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher
from company_curator.discovery.scorer import QualitativeScorer, ScoredCompany
from company_curator.discovery.screener import GrowthScreener
from company_curator.notifications.emailer import BaseNotifier
from company_curator.analysis.movement_notes import MovementNotesGenerator
from company_curator.watchlist.alerts import AlertManager
from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.monitor import GrowthMonitor
from company_curator.watchlist.price_tracker import PriceTracker


class DailyPipeline:
    """Orchestrates the full daily curation pipeline."""

    def __init__(
        self,
        config: Config,
        db: Database,
        fetcher: BaseDataFetcher,
        client: anthropic.Anthropic,
        notifier: BaseNotifier,
    ) -> None:
        self._config = config
        self._db = db
        self._fetcher = fetcher
        self._client = client
        self._notifier = notifier

    def run(self) -> str:
        """Run the complete daily pipeline. Returns the full report."""
        report_sections: list[str] = []
        today = datetime.now().strftime("%Y-%m-%d")

        report_sections.append(f"# Company Curator Daily Report — {today}\n")

        # Step 1: Discovery
        print("[Pipeline] Running discovery...")
        picks = self._run_discovery()
        if picks:
            report_sections.append(self._format_discovery_section(picks))
            # Step 2: Deep analysis on each pick
            print("[Pipeline] Running deep analysis...")
            for pick in picks:
                analysis = self._run_analysis(pick)
                report_sections.append(analysis)
                self._save_daily_pick(today, pick, analysis)
        else:
            report_sections.append("## Discovery\nNo new picks today.\n")

        # Step 3: Watchlist monitoring
        print("[Pipeline] Monitoring watchlist...")
        watchlist_section, alerts_section = self._run_watchlist_monitoring()
        report_sections.append(watchlist_section)
        if alerts_section:
            report_sections.append(alerts_section)

        full_report = "\n---\n\n".join(report_sections)

        # Step 4: Send email
        print("[Pipeline] Sending email report...")
        self._notifier.send(
            subject=f"Company Curator — {today}",
            body=full_report,
        )

        # Step 5: Save report to file
        self._save_report(today, full_report)

        print("[Pipeline] Daily pipeline complete.")
        return full_report

    def _format_discovery_section(self, picks: list[ScoredCompany]) -> str:
        """Format the discovery picks into a report section with watchlist links."""
        base_url = self._config.web.base_url
        lines = ["## Today's Top Picks\n"]
        for i, pick in enumerate(picks, 1):
            lines.append(
                f"{i}. **{pick.ticker}** — {pick.name} "
                f"(Score: {pick.score}/100) "
                f"— [Add to Watchlist]({base_url}/watchlist/add/{pick.ticker})"
            )
        return "\n".join(lines)

    def _run_discovery(self) -> list[ScoredCompany]:
        screener = GrowthScreener(self._fetcher)
        scorer = QualitativeScorer(self._client)

        candidates = screener.screen(count=20)
        if not candidates:
            return []

        return scorer.score_candidates(candidates, top_n=self._config.discovery.daily_picks)

    def _run_analysis(self, pick: ScoredCompany) -> str:
        deep_dive = DeepDiveAnalyzer(self._client, self._fetcher)
        peer_comp = PeerComparisonAnalyzer(self._client, self._fetcher)
        short_report = ShortReportAnalyzer(self._client, self._fetcher)

        sections = [f"## {pick.ticker} — {pick.name}\n"]
        sections.append(f"**Score:** {pick.score}/100\n**Reasoning:** {pick.reasoning}\n")

        sections.append("### Deep Dive\n")
        sections.append(deep_dive.analyze(pick.ticker))

        # Auto-detect competitors from the deep dive context
        sections.append("\n### Peer Comparison\n")
        info = self._fetcher.get_company_info(pick.ticker)
        competitors = self._find_competitors(pick.ticker)
        if len(competitors) >= 2:
            sections.append(peer_comp.analyze(pick.ticker, competitors[0], competitors[1]))
        else:
            sections.append("Insufficient competitor data for peer comparison.\n")

        sections.append("\n### Short Report (Risk Assessment)\n")
        sections.append(short_report.analyze(pick.ticker))

        return "\n".join(sections)

    def _find_competitors(self, ticker: str) -> list[str]:
        """Find 2 competitors for peer comparison using sector matching."""
        info = self._fetcher.get_company_info(ticker)
        if not info:
            return []

        # Simple competitor finding: same sector stocks from our universe
        from company_curator.data.fetcher import YFinanceDataFetcher
        universe = YFinanceDataFetcher._get_screening_universe().split()
        competitors: list[str] = []

        for t in universe:
            if t == ticker:
                continue
            comp_info = self._fetcher.get_company_info(t)
            if comp_info and comp_info.sector == info.sector:
                competitors.append(t)
            if len(competitors) >= 2:
                break

        return competitors

    def _run_watchlist_monitoring(self) -> tuple[str, str]:
        manager = WatchlistManager(self._db)
        monitor = GrowthMonitor(
            self._db,
            self._fetcher,
            price_threshold_pct=self._config.watchlist.min_price_growth_pct,
            revenue_threshold_pct=self._config.watchlist.min_revenue_growth_pct,
            monitoring_days=self._config.watchlist.monitoring_period_days,
        )
        alert_mgr = AlertManager(self._db)

        entries = manager.list_active()
        if not entries:
            return "## Watchlist\nNo companies on watchlist.\n", ""

        reports = monitor.evaluate_all(entries)

        # Record daily prices (both legacy and OHLCV)
        tickers = [e.ticker for e in entries]
        for entry in entries:
            monitor.record_daily_price(entry.ticker)

        tracker = PriceTracker(self._db, self._fetcher)
        tracker.record_daily_prices(tickers)

        # Generate movement notes for significant movers
        print("[Pipeline] Generating movement notes...")
        notes_gen = MovementNotesGenerator(self._client, self._fetcher, self._db)
        notes_gen.generate_daily_notes(tickers)

        # Check for alerts
        new_alerts = alert_mgr.check_and_create_alerts(reports)

        # Format watchlist section
        lines = ["## Watchlist Status\n"]
        for r in reports:
            status = "READY" if r.ready_for_investment else f"Day {r.days_watched}/90"
            lines.append(
                f"- **{r.ticker}** ({r.company_name}): "
                f"${r.current_price:.2f} ({r.price_change_pct:+.1f}%) — {status}"
            )
        watchlist_section = "\n".join(lines)

        # Format alerts section
        alerts_section = ""
        if new_alerts:
            alert_lines = ["## Investment Alerts\n"]
            for alert in new_alerts:
                alert_lines.append(f"**{alert.ticker}:** {alert.message}\n")
            alerts_section = "\n".join(alert_lines)

        return watchlist_section, alerts_section

    def _save_daily_pick(self, date: str, pick: ScoredCompany, analysis: str) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO daily_picks (date, ticker, company_name, score, reasoning, deep_dive)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, pick.ticker, pick.name, pick.score, pick.reasoning, analysis),
        )
        self._db.commit()

    def _save_report(self, date: str, report: str) -> None:
        reports_dir = self._config.reports_dir
        reports_dir.mkdir(exist_ok=True)
        report_path = reports_dir / f"report_{date}.md"
        report_path.write_text(report)
        print(f"[Pipeline] Report saved to {report_path}")
