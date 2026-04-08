"""
main.py — entry point for the Polymarket Agent.

Usage:
  make paper    → paper trading mode (safe, no real money)
  make live     → live trading (requires confirmation)
  make ingest   → update RAG with latest news
  make dashboard → open Streamlit UI
  make test     → run all tests
"""
import asyncio
import sys
import logging
import logging.config
import yaml
from pathlib import Path
from loguru import logger
from rich.console import Console
from rich.panel import Panel

console = Console()


def setup_logging() -> None:
    log_config_path = Path("config/logging.yaml")
    if log_config_path.exists():
        with open(log_config_path) as f:
            config = yaml.safe_load(f)
        try:
            logging.config.dictConfig(config)
        except Exception:
            pass  # fall back to default logging

    # Also ensure storage dir exists for log file
    Path("storage").mkdir(exist_ok=True)


def print_banner(mode: str, bankroll: float) -> None:
    console.print(Panel.fit(
        f"[bold cyan]Polymarket Agent[/bold cyan]\n"
        f"Mode: [bold {'red' if mode == 'LIVE' else 'yellow'}]{mode}[/bold {'red' if mode == 'LIVE' else 'yellow'}]\n"
        f"Bankroll: [bold green]${bankroll:.2f}[/bold green]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="cyan",
    ))


async def main() -> None:
    setup_logging()

    try:
        from config.settings import get_settings
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Config error: {e}[/red]")
        console.print("[yellow]Copy .env.example to .env and fill in your keys[/yellow]")
        sys.exit(1)

    mode = "LIVE" if settings.live_mode else "PAPER"
    bankroll = settings.max_total_exposure_usd  # use as proxy for starting bankroll

    print_banner(mode, bankroll)

    if settings.live_mode:
        console.print("[bold red]⚠️  LIVE MODE ACTIVE — real money at risk![/bold red]")
        console.print("[yellow]You have 5 seconds to Ctrl+C if this is wrong...[/yellow]")
        await asyncio.sleep(5)

    # Initialize database
    from storage.db import init_db
    init_db()
    logger.info("Database ready")

    # Run initial news ingestion for RAG (best-effort)
    try:
        from rag.ingester import run_ingestion
        logger.info("Running initial news ingestion...")
        result = await run_ingestion()
        logger.info(f"Ingested {result['news_ingested']} articles into RAG")
    except Exception as e:
        logger.warning(f"RAG ingestion skipped (optional): {e}")

    # Send startup alert
    try:
        from notifications.alerts import AlertManager
        alerts = AlertManager()
        await alerts.send_startup(mode, bankroll)
    except Exception:
        pass  # alerts are optional

    # Start the main trading loop
    from agents.orchestrator import run_scheduler
    await run_scheduler(bankroll_usd=bankroll)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped by user.[/yellow]")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise
