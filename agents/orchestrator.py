"""
Orchestrator Agent — the conductor.
Owns the main trading cycle. Coordinates all other agents.
Runs on a schedule (APScheduler) or can be triggered manually.
"""
import asyncio
from datetime import datetime
from loguru import logger

from config.settings import get_settings
from config.constants import CYCLE_INTERVAL_SECONDS
from storage.models import SignalType
from data.polymarket_client import PolymarketClient
from agents.analyst import AnalystAgent
from agents.arb_scanner import run_arb_scan
from agents.risk_manager import RiskManagerAgent
from agents.executor import ExecutorAgent
from agents.monitor import MonitorAgent


class OrchestratorAgent:
    def __init__(self, bankroll_usd: float = 100.0):
        self.settings = get_settings()
        self.bankroll_usd = bankroll_usd

        # Analyst is optional - only initialize if API key is available
        self.analyst = None
        try:
            self.analyst = AnalystAgent()
            logger.info("Analyst agent initialized - full analysis available")
        except ValueError as e:
            logger.warning(f"Analyst agent unavailable: {e}")
            logger.info("Running in arbitrage-only mode (no directional trading)")

        self.risk_manager = RiskManagerAgent(bankroll_usd=bankroll_usd)
        self.executor = ExecutorAgent()
        self.monitor = MonitorAgent(bankroll_usd=bankroll_usd)
        self._cycle_count = 0

    async def run_cycle(self) -> dict:
        """
        One full trading cycle:
          1. Check circuit breakers
          2. Fetch active markets
          3. Run arb scanner (free money first)
          4. Filter markets for analysis
          5. Run analyst on each market
          6. Risk check each signal
          7. Execute approved trades
          8. Return cycle summary
        """
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        logger.info(f"━━━ Cycle #{self._cycle_count} starting ━━━")

        summary = {
            "cycle": self._cycle_count,
            "started_at": cycle_start.isoformat(),
            "markets_fetched": 0,
            "arb_found": 0,
            "arb_executed": 0,
            "signals_generated": 0,
            "trades_approved": 0,
            "trades_executed": 0,
            "errors": [],
        }

        # ── 1. Circuit breaker check ─────────────────────────
        halted, reason = self.monitor.check_circuit_breakers()
        if halted:
            logger.warning(f"Cycle skipped — trading halted: {reason}")
            summary["halted"] = True
            summary["halt_reason"] = reason
            return summary

        # ── 2. Fetch markets ─────────────────────────────────
        try:
            async with PolymarketClient() as poly:
                markets = await poly.get_active_markets()
            summary["markets_fetched"] = len(markets)
            logger.info(f"Fetched {len(markets)} active markets")
        except Exception as e:
            logger.error(f"Market fetch failed: {e}")
            summary["errors"].append(f"market_fetch: {e}")
            return summary

        if not markets:
            logger.warning("No markets fetched this cycle")
            return summary

        # ── 3. Arb scan (no API cost, run on all markets) ────
        try:
            arb_opportunities = await run_arb_scan(markets)
            summary["arb_found"] = len(arb_opportunities)

            # Build market lookup for risk manager
            market_lookup = {m.market_id: m for m in markets}

            for opp in arb_opportunities:
                market = market_lookup.get(opp.market_id)
                if not market:
                    continue
                decision = self.risk_manager.evaluate_arb(opp, market)
                if decision.approved:
                    try:
                        records = await self.executor.execute_arb(decision, market)
                        summary["arb_executed"] += len(records)
                        await self.monitor.notify_arb(
                            opp.question, opp.profit_cents, opp.arb_type.value
                        )
                    except Exception as e:
                        logger.error(f"Arb execution failed: {e}")
                        summary["errors"].append(f"arb_exec: {e}")
        except Exception as e:
            logger.error(f"Arb scan failed: {e}")
            summary["errors"].append(f"arb_scan: {e}")

        # ── 4. Filter markets for analyst ────────────────────
        if self.analyst:
            try:
                selected_markets = await self.analyst.filter_markets(markets)
            except Exception as e:
                logger.warning(f"Market filter failed, using top 15: {e}")
                selected_markets = markets[:15]
        else:
            # No analyst available - skip directional trading
            selected_markets = []
            logger.info("Skipping market analysis (no analyst available)")

        # ── 5 & 6. Analyse + risk check each market ──────────
        signals = []
        if self.analyst and selected_markets:
            for market in selected_markets:
                try:
                    signal = await self.analyst.analyse_market(market)
                    if signal is None:
                        continue
                    summary["signals_generated"] += 1

                    decision = self.risk_manager.evaluate_signal(signal, market)
                    if decision.approved:
                        signals.append((decision, market))
                        summary["trades_approved"] += 1

                    # Small delay between API calls to be respectful
                    await asyncio.sleep(1.5)

                except Exception as e:
                    logger.error(f"Analysis failed for {market.market_id}: {e}")
                    summary["errors"].append(f"analysis:{market.market_id}: {e}")
        else:
            logger.info("No analyst available - skipping signal generation")

        # ── 7. Execute approved trades ───────────────────────
        for decision, market in signals:
            try:
                record = await self.executor.execute(decision, market)
                summary["trades_executed"] += 1
                await self.monitor.notify_trade(
                    question=decision.question,
                    side=decision.side.value,
                    stake=decision.stake_usd,
                    edge=decision.edge,
                    mode=self.executor.mode.value,
                )
            except Exception as e:
                logger.error(f"Execution failed for {decision.market_id}: {e}")
                summary["errors"].append(f"exec:{decision.market_id}: {e}")

        # ── 8. Cycle summary ─────────────────────────────────
        duration = (datetime.utcnow() - cycle_start).total_seconds()
        summary["duration_seconds"] = round(duration, 1)
        logger.info(
            f"━━━ Cycle #{self._cycle_count} complete in {duration:.1f}s | "
            f"arb={summary['arb_executed']} trades={summary['trades_executed']} "
            f"errors={len(summary['errors'])} ━━━"
        )
        return summary

    def get_status(self) -> dict:
        return {
            "cycle_count": self._cycle_count,
            "monitor": self.monitor.get_status_summary(),
            "mode": self.executor.mode.value,
        }


async def run_scheduler(bankroll_usd: float = 100.0) -> None:
    """
    Run the orchestrator on a repeating schedule.
    Uses APScheduler for reliable cron-style execution.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    settings = get_settings()
    orchestrator = OrchestratorAgent(bankroll_usd=bankroll_usd)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        orchestrator.run_cycle,
        trigger="interval",
        seconds=settings.cycle_interval_seconds,
        id="trading_cycle",
        max_instances=1,  # never run two cycles simultaneously
        coalesce=True,
    )
    scheduler.start()

    mode = "LIVE" if settings.live_mode else "PAPER"
    logger.success(f"Scheduler started | mode={mode} | interval={settings.cycle_interval_seconds}s")

    # Run first cycle immediately
    await orchestrator.run_cycle()

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
            status = orchestrator.get_status()
            logger.debug(f"Heartbeat | cycles={status['cycle_count']}")
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Orchestrator stopped")
