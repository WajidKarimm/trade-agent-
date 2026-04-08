# Polymarket Agent

Autonomous AI trading agent for Polymarket prediction markets.

## Architecture

5 agents: **Orchestrator → Data Collector → Analyst (Claude) → Risk Manager → Executor**  
Plus: **Monitor** (watchdog), **Arb Scanner** (pure math, no AI cost)

## Quick Start

```bash
# 1. Install
make install

# 2. Edit your keys
cp .env.example .env
nano .env   # add ANTHROPIC_API_KEY at minimum

# 3. Paper trade (no real money)
make paper

# 4. Watch the dashboard
make dashboard   # open http://localhost:8501

# 5. Only after 2+ weeks of validated paper trading:
make live
```

## Free APIs Used

| Service          | Purpose                    | Cost     |
|------------------|----------------------------|----------|
| Polymarket Gamma | Market data                | Free     |
| Polymarket CLOB  | Order book + execution     | Free     |
| Kalshi API       | Cross-venue arb detection  | Free     |
| GDELT            | Global news database       | Free     |
| RSS Feeds        | BBC/Reuters/AP/Guardian    | Free     |
| Reddit PRAW      | Social sentiment           | Free     |
| Chroma DB        | Local vector database      | Free     |
| sentence-transformers | Local embeddings      | Free     |
| SQLite           | Trade history              | Free     |
| Telegram Bot     | Alerts                     | Free     |
| Claude API       | Analyst brain              | ~$0.50/day |

## Safety Rules

- `LIVE_MODE=false` by default — always paper trade first
- Kelly fraction set to 0.25 (quarter Kelly — conservative)
- Max 5% of bankroll per trade (hardcoded in `risk/limits.py`)
- Max 20% drawdown triggers automatic halt
- LLM cannot modify any risk parameters

## Project Structure

```
polymarket-agent/
├── agents/          # orchestrator, analyst, arb_scanner, risk_manager, executor, monitor
├── data/            # polymarket, kalshi, news (GDELT), rss, social clients
├── rag/             # chroma vector DB, embedder, ingester, retriever
├── risk/            # kelly sizing, hardcoded limits, portfolio tracker
├── prompts/         # superforecaster prompt + others (versioned as text files)
├── storage/         # SQLite DB, Chroma files, paper trade log
├── dashboard/       # Streamlit P&L + signal UI
├── notifications/   # Telegram alerts
├── tests/           # pytest unit tests
└── config/          # settings (pydantic), constants, logging
```

## Key Design Decisions

1. **Paper mode first** — `LIVE_MODE=false` is default. You need to manually confirm to go live.
2. **Arb scanner runs before analyst** — free mathematical edge before spending API tokens.
3. **Prompts are text files** — improve `prompts/superforecaster.txt` without touching Python.
4. **Risk layer is deterministic** — Kelly + hardcoded limits. The LLM never touches sizing.
5. **RAG is local** — sentence-transformers + Chroma run on your machine. Zero cloud cost.

## Disclaimer

This software is for educational purposes. Prediction market trading involves real financial risk.
Always paper trade first. Never risk money you cannot afford to lose.
Check your jurisdiction's laws before trading on Polymarket.
