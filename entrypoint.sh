#!/bin/sh
# Entrypoint for the Dockerised Ollama server.
#
# Starts `ollama serve` in the background, waits for it to accept
# requests, optionally pre-pulls any models listed in OLLAMA_PULL_MODELS,
# then hands control back to the server process. Termination signals are
# forwarded so `docker compose down` shuts the server down cleanly.
set -e

# Start the Ollama server in the background.
ollama serve &
OLLAMA_PID=$!

# Forward termination signals to the server for a clean shutdown.
trap 'kill -TERM "$OLLAMA_PID" 2>/dev/null' TERM INT

# Wait until the server is ready to accept requests (give up after ~60s
# so a broken start surfaces instead of hanging forever).
echo "Waiting for the Ollama server to start..."
tries=0
until ollama list >/dev/null 2>&1; do
  tries=$((tries + 1))
  if [ "$tries" -gt 60 ]; then
    echo "Ollama server did not become ready in time." >&2
    exit 1
  fi
  sleep 1
done
echo "Ollama server is ready."

# Optionally pre-pull models listed in OLLAMA_PULL_MODELS (space or comma
# separated). Already-downloaded models are a no-op, so this is cheap.
if [ -n "$OLLAMA_PULL_MODELS" ]; then
  for model in $(echo "$OLLAMA_PULL_MODELS" | tr ',' ' '); do
    echo "Pulling model: $model"
    ollama pull "$model" || echo "Warning: failed to pull $model" >&2
  done
fi

# Hand control back to the server process (keeps the container alive).
wait "$OLLAMA_PID"
