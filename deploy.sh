#!/bin/bash

# Princess - Quick Deploy Script
# This script helps you deploy Princess to various platforms

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     👸  Princess - XtraBrides of Lagos AI Assistant  👗     ║"
echo "║                                                              ║"
echo "║                    Quick Deploy Script                       ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Choose your deployment platform:"
echo ""
echo "  1) 🚀 Render.com (Recommended - Free tier available)"
echo "  2) 🚂 Railway.app (Easiest - Auto-deploy)"
echo "  3) 🐳 Docker (Local container)"
echo "  4) 💻 Local Development (Start now)"
echo "  5) 📖 Show deployment links"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
  1)
    echo ""
    echo "📝 Deploying to Render.com..."
    echo ""
    echo "Steps:"
    echo "1. Go to: https://render.com/signup"
    echo "2. Click 'New +' → 'Web Service'"
    echo "3. Connect your repository"
    echo "4. Use these settings:"
    echo "   - Build Command: pip install -r requirements.txt"
    echo "   - Start Command: uvicorn princess_app:app --host 0.0.0.0 --port \$PORT"
    echo "   - Environment: Add OPENAI_API_KEY"
    echo ""
    echo "Your link will be: https://princess-xtrabrides.onrender.com"
    echo ""
    read -p "Press Enter to open Render.com..." 
    open "https://render.com/signup" 2>/dev/null || echo "Visit: https://render.com/signup"
    ;;
    
  2)
    echo ""
    echo "🚂 Deploying to Railway.app..."
    echo ""
    echo "Steps:"
    echo "1. Go to: https://railway.app"
    echo "2. Click 'Start a New Project'"
    echo "3. Choose 'Deploy from GitHub repo'"
    echo "4. Add environment variable: OPENAI_API_KEY"
    echo ""
    echo "Your link will be auto-generated!"
    echo ""
    read -p "Press Enter to open Railway.app..." 
    open "https://railway.app" 2>/dev/null || echo "Visit: https://railway.app"
    ;;
    
  3)
    echo ""
    echo "🐳 Starting Princess with Docker..."
    echo ""
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker first:"
        echo "   https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if [ ! -f .env ]; then
        echo "⚠️  .env file not found. Creating template..."
        echo "OPENAI_API_KEY=your_openai_key_here" > .env
        echo "Please edit .env file and add your OpenAI API key"
        exit 1
    fi
    
    echo "Building Docker image..."
    docker build -t princess-xtrabrides .
    
    echo ""
    echo "Starting Princess container..."
    docker-compose up -d
    
    echo ""
    echo "✅ Princess is running!"
    echo "   Local: http://localhost:8001"
    echo ""
    echo "To view logs: docker-compose logs -f"
    echo "To stop: docker-compose down"
    ;;
    
  4)
    echo ""
    echo "💻 Starting Princess locally..."
    echo ""
    
    # Check if .env exists
    if [ ! -f .env ]; then
        echo "❌ .env file not found!"
        echo "Please create .env file with: OPENAI_API_KEY=your_key"
        exit 1
    fi
    
    # Check if virtualenv exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    
    echo ""
    echo "✅ Starting Princess..."
    echo ""
    echo "Princess will be available at:"
    echo "  🌐 http://localhost:8001"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""
    
    python3 princess_app.py
    ;;
    
  5)
    echo ""
    echo "📖 Deployment Links & Resources:"
    echo ""
    echo "Hosting Platforms:"
    echo "  • Render:     https://render.com"
    echo "  • Railway:    https://railway.app"  
    echo "  • Vercel:     https://vercel.com"
    echo "  • Fly.io:     https://fly.io"
    echo "  • Replit:     https://replit.com"
    echo ""
    echo "Documentation:"
    echo "  • Full Guide: PRINCESS_README.md"
    echo "  • Quick Deploy: DEPLOYMENT_GUIDE.md"
    echo ""
    echo "OpenAI:"
    echo "  • Get API Key: https://platform.openai.com/api-keys"
    echo "  • Pricing: https://openai.com/api/pricing"
    echo ""
    ;;
    
  *)
    echo ""
    echo "❌ Invalid choice. Please run the script again."
    exit 1
    ;;
esac

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "💡 Tips:"
echo "  • Make sure OPENAI_API_KEY environment variable is set"
echo "  • Princess uses GPT-4o-mini (fast & cost-effective)"
echo "  • Update knowledge base in config/xtrabrides_knowledge.json"
echo ""
echo "📞 Support:"
echo "  XtraBrides of Lagos: +234 810 618 0911"
echo "  Email: xtrabrideslagos@yahoo.com"
echo ""
echo "════════════════════════════════════════════════════════════════"
