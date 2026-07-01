#!/usr/bin/env bash
# Pull the models required by MuminMate.
# Run once before starting the application.
set -e

echo "Pulling llama3.1:7b..."
ollama pull llama3.1:7b

echo "Pulling nomic-embed-text..."
ollama pull nomic-embed-text

echo "Done. Both models are ready."