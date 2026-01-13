#!/bin/bash

# Ollama Cloud Setup Script for RAG Transcript
# This script will guide you through setting up Ollama Cloud

set -e

echo "🚀 Ollama Cloud Setup for RAG Transcript"
echo "=========================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "📦 Ollama is not installed. Installing now..."
    echo ""
    echo "Please choose your installation method:"
    echo "1. Homebrew (recommended for macOS)"
    echo "2. Official installer script"
    read -p "Enter choice (1 or 2): " choice

    case $choice in
        1)
            echo "Installing via Homebrew..."
            brew install ollama
            ;;
        2)
            echo "Installing via official script..."
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        *)
            echo "❌ Invalid choice. Please run script again."
            exit 1
            ;;
    esac
else
    echo "✅ Ollama is already installed"
    ollama --version
fi

echo ""
echo "🔐 Step 1: Sign in to Ollama Cloud"
echo "-----------------------------------"
echo "This will open your browser to sign in or create an account."
echo "After signing in, return to this terminal."
echo ""
read -p "Press Enter to continue..."

ollama signin

echo ""
echo "✅ Signed in successfully!"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/version &> /dev/null; then
    echo "🔄 Step 2: Starting Ollama server..."
    echo "------------------------------------"

    # Start Ollama in background
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!

    echo "Waiting for Ollama to start..."
    sleep 3

    if curl -s http://localhost:11434/api/version &> /dev/null; then
        echo "✅ Ollama server started successfully (PID: $OLLAMA_PID)"
    else
        echo "❌ Failed to start Ollama server. Check /tmp/ollama.log"
        exit 1
    fi
else
    echo "✅ Ollama server is already running"
fi

echo ""
echo "📥 Step 3: Pulling Cloud Models"
echo "--------------------------------"
echo "Pulling qwen3-vl:235b-instruct-cloud (cloud model - minimal download)"

ollama pull qwen3-vl:235b-instruct-cloud

echo ""
echo "Pulling additional cloud models..."
ollama pull gpt-oss:120b-cloud
ollama pull qwen3-coder:480b-cloud

echo ""
echo "✅ All models pulled successfully!"
echo ""

echo "🧪 Step 4: Testing Cloud Model"
echo "-------------------------------"
echo "Sending test prompt to qwen3-vl:235b-instruct-cloud..."
echo ""

ollama run qwen3-vl:235b-instruct-cloud "Say 'Hello from Ollama Cloud!' and nothing else."

echo ""
echo ""
echo "🔍 Step 5: Verifying Docker Connectivity"
echo "-----------------------------------------"

if docker ps | grep -q rag_transcript_app; then
    echo "Testing if Docker container can reach Ollama..."
    if docker exec rag_transcript_app curl -s http://host.docker.internal:11434/api/version &> /dev/null; then
        echo "✅ Docker can connect to Ollama!"
    else
        echo "⚠️  Docker cannot connect to Ollama"
        echo "This is usually okay - Ollama might need to be restarted"
        echo "Try: killall ollama && ollama serve"
    fi
else
    echo "⚠️  Docker container not running. Start with: docker-compose up -d"
fi

echo ""
echo "✨ Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Go to http://localhost:3000/conversations"
echo "2. Select 'Qwen3 VL 235B (Ollama Cloud)' from the model dropdown"
echo "3. Send a test message"
echo "4. Enjoy free cloud inference! 🎉"
echo ""
echo "Note: If you restart your computer, you'll need to run 'ollama serve' again."
echo ""
echo "Troubleshooting:"
echo "- If errors occur, check /tmp/ollama.log"
echo "- Ensure Ollama is running: ps aux | grep ollama"
echo "- Restart Ollama: killall ollama && ollama serve"
echo ""
