#!/usr/bin/env bash
# run_pipeline.sh – Local development pipeline runner
# Usage: ./scripts/run_pipeline.sh [--reset-db] [--diff <file>]

set -euo pipefail

RESET_DB=false
DIFF_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --reset-db) RESET_DB=true; shift ;;
        --diff) DIFF_FILE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "========================================="
echo "  AI-Driven QA Platform – Local Runner"
echo "========================================="

# Ensure uv is available
if ! command -v uv &>/dev/null; then
    echo "[ERROR] 'uv' not found. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Sync deps
echo "[1/4] Installing dependencies..."
uv sync

# Reset ChromaDB if requested
if [ "$RESET_DB" = true ]; then
    echo "[2/4] Resetting ChromaDB..."
    rm -rf data/chroma
fi

# Check Ollama connectivity
echo "[2/4] Checking Ollama..."
if ! curl -sf http://localhost:11434/api/tags > /dev/null; then
    echo "[WARN] Ollama not reachable at http://localhost:11434 – start with: ollama serve"
fi

# Start the API server in background if not already running
if ! curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "[3/4] Starting API server..."
    uv run python main.py &
    API_PID=$!
    sleep 3
    echo "      API server started (PID=$API_PID)"
else
    echo "[3/4] API server already running."
    API_PID=""
fi

# Run the pipeline with a diff if provided
if [ -n "$DIFF_FILE" ]; then
    if [ ! -f "$DIFF_FILE" ]; then
        echo "[ERROR] Diff file not found: $DIFF_FILE"
        exit 1
    fi
    echo "[4/4] Submitting diff to pipeline..."
    DIFF_CONTENT=$(cat "$DIFF_FILE")
    RESPONSE=$(curl -sf -X POST http://localhost:8000/api/pipeline/run \
        -H "Content-Type: application/json" \
        -d "{\"diff_text\": $(echo "$DIFF_CONTENT" | jq -Rs .)}")
    RUN_ID=$(echo "$RESPONSE" | jq -r '.run_id')
    echo "      Run ID: $RUN_ID"
    echo "      Streaming events (Ctrl+C to stop):"
    curl -N "http://localhost:8000/api/pipeline/status/$RUN_ID"
else
    echo "[4/4] No diff provided. Open http://localhost:8000/api/docs to submit manually."
    echo "      Frontend: cd frontend && npm run dev"
fi

# Clean up if we started the API
if [ -n "${API_PID:-}" ]; then
    echo ""
    read -r -p "Press [Enter] to stop the API server..."
    kill "$API_PID" 2>/dev/null || true
fi
