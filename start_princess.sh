#!/bin/bash
# Start Princess - XtraBrides of Lagos AI Assistant

echo "Starting Princess - XtraBrides of Lagos AI Assistant..."
echo "=================================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file with your OPENAI_API_KEY"
    exit 1
fi

# Check if OpenAI API key is set
if ! grep -q "OPENAI_API_KEY" .env; then
    echo "Warning: OPENAI_API_KEY not found in .env file"
    echo "Please add your OpenAI API key to the .env file"
fi

# Set default port if not specified
export PRINCESS_PORT=${PRINCESS_PORT:-8001}

echo "Princess will be available at:"
echo "  Local: http://localhost:$PRINCESS_PORT"
echo "  Network: http://0.0.0.0:$PRINCESS_PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================================="
echo ""

# Start the server
cd "$(dirname "$0")"
python3 princess_app.py
