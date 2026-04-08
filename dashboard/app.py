"""
Streamlit dashboard — run with: make dashboard
Live view of P&L, signals, arb log, open positions.
"""
import sqlite3
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings

st.set_page_config(
    page_title="Polymarket Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = get_settings()

# ── Sidebar ───────────────────────────────────────────────
st.sidebar.title("Polymarket Agent")
mode_color = "🔴" if settings.live_mode else "🟡"
st.sidebar.markdown(f"**Mode:** {mode_color} {'LIVE' if settings.live_mode else 'PAPER'}")
st.sidebar.markdown("---")
page = st.sidebar.radio("View", ["Overview", "Signals", "Paper Trades", "Arb Log"])


def load_db(query: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(settings.sqlite_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ── Overview ─────────────────────────────────────────────
if page == "Overview":
    st.title("Portfolio Overview")

    trades_df = load_db("SELECT * FROM trades WHERE resolved=1")
    open_df   = load_db("SELECT * FROM trades WHERE resolved=0")

    col1, col2, col3, col4 = st.columns(4)
    total_pnl   = trades_df["pnl_usd"].sum() if not trades_df.empty and "pnl_usd" in trades_df else 0.0
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df["pnl_usd"] > 0]) if not trades_df.empty and "pnl_usd" in trades_df else 0
    win_rate = wins / total_trades if total_trades > 0 else 0.0

    col1.metric("Total P&L", f"${total_pnl:.2f}", delta=f"${total_pnl:.2f}")
    col2.metric("Win Rate", f"{win_rate:.1%}")
    col3.metric("Total Trades", total_trades)
    col4.metric("Open Positions", len(open_df))

    if not trades_df.empty and "pnl_usd" in trades_df:
        trades_df["created_at"] = pd.to_datetime(trades_df["created_at"])
        trades_df = trades_df.sort_values("created_at")
        trades_df["cumulative_pnl"] = trades_df["pnl_usd"].cumsum()
        st.subheader("Cumulative P&L")
        st.line_chart(trades_df.set_index("created_at")["cumulative_pnl"])

    if not open_df.empty:
        st.subheader("Open Positions")
        st.dataframe(
            open_df[["question", "side", "stake_usd", "entry_price", "signal_type", "created_at"]],
            use_container_width=True,
        )


# ── Signals ───────────────────────────────────────────────
elif page == "Signals":
    st.title("Analyst Signals")
    df = load_db("SELECT * FROM signals ORDER BY created_at DESC LIMIT 100")
    if df.empty:
        st.info("No signals yet. Start the agent with: make paper")
    else:
        st.dataframe(df, use_container_width=True)


# ── Paper Trades ──────────────────────────────────────────
elif page == "Paper Trades":
    st.title("Paper Trade Log")
    df = load_db("SELECT * FROM trades WHERE mode='PAPER' ORDER BY created_at DESC LIMIT 200")
    if df.empty:
        st.info("No paper trades yet.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Paper Trades", len(df))
        col2.metric("Total Paper Staked", f"${df['stake_usd'].sum():.2f}")
        st.dataframe(df, use_container_width=True)


# ── Arb Log ───────────────────────────────────────────────
elif page == "Arb Log":
    st.title("Arbitrage Opportunities")
    df = load_db("SELECT * FROM arb_log ORDER BY created_at DESC LIMIT 200")
    if df.empty:
        st.info("No arb opportunities found yet.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Arb Opportunities Found", len(df))
        col2.metric("Avg Profit", f"{df['profit_cents'].mean():.1f}¢")
        st.subheader("Profit Distribution")
        st.bar_chart(df["profit_cents"].value_counts().sort_index())
        st.dataframe(df, use_container_width=True)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh"):
    st.rerun()
