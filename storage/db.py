"""
SQLite database — all persistent state.
Single file, no server, works anywhere.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from config.settings import get_settings
from storage.models import TradeRecord, TradeMode, Side, SignalType


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id       TEXT NOT NULL,
                question        TEXT NOT NULL,
                side            TEXT NOT NULL,
                stake_usd       REAL NOT NULL,
                entry_price     REAL NOT NULL,
                edge            REAL NOT NULL,
                confidence      REAL NOT NULL,
                signal_type     TEXT NOT NULL,
                mode            TEXT NOT NULL DEFAULT 'PAPER',
                tx_hash         TEXT DEFAULT '',
                fill_price      REAL,
                pnl_usd         REAL,
                resolved        INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL,
                resolved_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS signals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id       TEXT NOT NULL,
                question        TEXT NOT NULL,
                my_prob_yes     REAL NOT NULL,
                market_prob_yes REAL NOT NULL,
                edge            REAL NOT NULL,
                confidence      REAL NOT NULL,
                side            TEXT NOT NULL,
                signal_type     TEXT NOT NULL,
                reasoning       TEXT DEFAULT '',
                acted_on        INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS arb_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id       TEXT NOT NULL,
                question        TEXT NOT NULL,
                arb_type        TEXT NOT NULL,
                yes_price       REAL NOT NULL,
                no_price        REAL NOT NULL,
                profit_cents    REAL NOT NULL,
                venue_a         TEXT DEFAULT 'polymarket',
                venue_b         TEXT DEFAULT '',
                acted_on        INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
            CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
            CREATE INDEX IF NOT EXISTS idx_signals_market ON signals(market_id);
        """)
        conn.commit()
        logger.info("Database initialized")
    finally:
        conn.close()


def save_trade(trade: TradeRecord) -> int:
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO trades
            (market_id, question, side, stake_usd, entry_price, edge,
             confidence, signal_type, mode, tx_hash, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade.market_id, trade.question, trade.side.value,
            trade.stake_usd, trade.entry_price, trade.edge,
            trade.confidence, trade.signal_type.value, trade.mode.value,
            trade.tx_hash, trade.created_at.isoformat()
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_open_trades(mode: Optional[TradeMode] = None) -> list[dict]:
    conn = get_connection()
    try:
        if mode:
            rows = conn.execute(
                "SELECT * FROM trades WHERE resolved=0 AND mode=?",
                (mode.value,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE resolved=0"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_trade_stats() -> dict:
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(pnl_usd) as total_pnl,
                AVG(stake_usd) as avg_stake
            FROM trades WHERE resolved=1
        """).fetchone()
        total = row["total"] or 0
        wins = row["wins"] or 0
        return {
            "total_trades": total,
            "wins": wins,
            "win_rate": wins / total if total > 0 else 0.0,
            "total_pnl_usd": row["total_pnl"] or 0.0,
            "avg_stake_usd": row["avg_stake"] or 0.0,
        }
    finally:
        conn.close()


def log_arb(market_id: str, question: str, arb_type: str,
            yes_price: float, no_price: float, profit_cents: float,
            venue_b: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO arb_log
            (market_id, question, arb_type, yes_price, no_price,
             profit_cents, venue_b, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (market_id, question, arb_type, yes_price, no_price,
              profit_cents, venue_b, datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()
