"""
Executor Agent — the ONLY agent that touches money.
Two modes:
  PAPER: logs the trade to JSONL + SQLite, no real orders
  LIVE:  calls Polymarket CLOB to place real orders
The mode is set by LIVE_MODE env var. LLM cannot change it.
"""
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

from config.settings import get_settings
from storage.models import (
    TradeDecision, TradeRecord, TradeMode, Side,
    MarketSnapshot, SignalType
)
from storage.db import save_trade


class ExecutorAgent:
    def __init__(self):
        self.settings = get_settings()
        self.mode = TradeMode.LIVE if self.settings.live_mode else TradeMode.PAPER
        log_path = Path(self.settings.dry_run_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._paper_log = open(log_path, "a") if self.mode == TradeMode.PAPER else None
        logger.info(f"Executor initialized in {self.mode.value} mode")

    def __del__(self):
        if self._paper_log:
            self._paper_log.close()

    async def execute(
        self,
        decision: TradeDecision,
        market: MarketSnapshot,
    ) -> TradeRecord:
        """
        Execute a trade decision.
        Routes to paper or live based on LIVE_MODE setting.
        """
        if not decision.approved:
            raise ValueError(f"Attempted to execute rejected trade: {decision.rejection_reason}")

        entry_price = market.yes_price if decision.side == Side.YES else market.no_price

        if self.mode == TradeMode.PAPER:
            return await self._paper_execute(decision, entry_price)
        else:
            return await self._live_execute(decision, market, entry_price)

    async def _paper_execute(
        self,
        decision: TradeDecision,
        entry_price: float,
    ) -> TradeRecord:
        """Log trade to paper record — no real money moves."""
        record = TradeRecord(
            market_id=decision.market_id,
            question=decision.question,
            side=decision.side,
            stake_usd=decision.stake_usd,
            entry_price=entry_price,
            edge=decision.edge,
            confidence=decision.confidence,
            signal_type=decision.signal_type,
            mode=TradeMode.PAPER,
            tx_hash="PAPER",
        )

        trade_id = save_trade(record)
        record.id = trade_id

        # Write to JSONL log for easy inspection
        if self._paper_log:
            self._paper_log.write(json.dumps({
                "id": trade_id,
                "market_id": decision.market_id,
                "question": decision.question,
                "side": decision.side.value,
                "stake_usd": decision.stake_usd,
                "entry_price": entry_price,
                "edge": decision.edge,
                "confidence": decision.confidence,
                "signal_type": decision.signal_type.value,
                "timestamp": datetime.utcnow().isoformat(),
            }) + "\n")
            self._paper_log.flush()

        logger.info(
            f"PAPER TRADE | {decision.side.value} ${decision.stake_usd:.2f} "
            f"@ {entry_price:.3f} | {decision.question[:50]}"
        )
        return record

    async def _live_execute(
        self,
        decision: TradeDecision,
        market: MarketSnapshot,
        entry_price: float,
    ) -> TradeRecord:
        """Place a real order on Polymarket CLOB."""
        logger.warning(f"LIVE ORDER | {decision.side.value} ${decision.stake_usd:.2f} | {decision.question[:50]}")

        try:
            from data.polymarket_client import PolymarketClient
            async with PolymarketClient() as client:
                result = await client.place_order(
                    market_id=decision.market_id,
                    side=decision.side.value,
                    amount_usd=decision.stake_usd,
                    price=entry_price,
                )

            tx_hash = result.get("orderID", result.get("transactionHash", ""))
            fill_price = float(result.get("price", entry_price))

            record = TradeRecord(
                market_id=decision.market_id,
                question=decision.question,
                side=decision.side,
                stake_usd=decision.stake_usd,
                entry_price=entry_price,
                edge=decision.edge,
                confidence=decision.confidence,
                signal_type=decision.signal_type,
                mode=TradeMode.LIVE,
                tx_hash=tx_hash,
                fill_price=fill_price,
            )
            trade_id = save_trade(record)
            record.id = trade_id
            logger.success(f"LIVE ORDER FILLED | tx={tx_hash} | id={trade_id}")
            return record

        except Exception as e:
            logger.error(f"Live order FAILED: {e}")
            raise

    async def execute_arb(
        self,
        decision: TradeDecision,
        market: MarketSnapshot,
    ) -> list[TradeRecord]:
        """
        For Dutch book arb: place BOTH YES and NO sides.
        For cross-venue arb: caller handles multi-venue routing.
        """
        records = []

        if decision.signal_type == SignalType.ARB_DUTCH:
            # Buy YES side
            yes_decision = TradeDecision(
                market_id=decision.market_id,
                question=decision.question,
                approved=True,
                side=Side.YES,
                stake_usd=decision.stake_usd,
                edge=decision.edge,
                confidence=decision.confidence,
                signal_type=decision.signal_type,
            )
            # Buy NO side
            no_decision = TradeDecision(
                market_id=decision.market_id,
                question=decision.question,
                approved=True,
                side=Side.NO,
                stake_usd=decision.stake_usd,
                edge=decision.edge,
                confidence=decision.confidence,
                signal_type=decision.signal_type,
            )
            records.append(await self.execute(yes_decision, market))
            records.append(await self.execute(no_decision, market))
        else:
            records.append(await self.execute(decision, market))

        return records
