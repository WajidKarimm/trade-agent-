.PHONY: install run paper live test dashboard ingest clean lint

# ── Setup ─────────────────────────────────────────────────
install:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements-dev.txt
	cp -n .env.example .env || true
	@echo "✓ Installed. Edit .env with your keys then run: make paper"

# ── Run modes ─────────────────────────────────────────────
paper:
	@echo "▶ Starting agent in PAPER (dry-run) mode..."
	LIVE_MODE=false python main.py

live:
	@echo ""
	@echo "⚠️  WARNING: This will trade with REAL money!"
	@read -p "Type 'yes I understand' to continue: " confirm; \
	if [ "$$confirm" = "yes I understand" ]; then \
		LIVE_MODE=true python main.py; \
	else \
		echo "Aborted."; \
	fi

# ── Dashboard ─────────────────────────────────────────────
dashboard:
	streamlit run dashboard/app.py --server.port 8501

# ── RAG ingestion ─────────────────────────────────────────
ingest:
	python -c "from rag.ingester import run_ingestion; import asyncio; asyncio.run(run_ingestion())"

# ── Testing ───────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-arb:
	pytest tests/test_arb.py -v

test-kelly:
	pytest tests/test_kelly.py -v

# ── Code quality ──────────────────────────────────────────
lint:
	ruff check . --fix

# ── Cleanup ───────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned"
