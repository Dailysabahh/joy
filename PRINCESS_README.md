# Princess - XtraBrides of Lagos AI Customer Assistant

## Overview

Princess is an intelligent AI customer assistant for XtraBrides of Lagos, a prestigious luxury bridal couture brand in Lagos, Nigeria. She provides 24/7 customer support, answers questions about collections, pricing, and helps book consultations.

## Features

- **Complete Business Knowledge**: Princess knows everything about XtraBrides of Lagos including:
  - All bridal and non-bridal collections
  - Detailed pricing information (₦350,000 - ₦15,000,000+)
  - Celebrity clientele (Davido, Tiwa Savage, Funke Akindele, etc.)
  - Booking policies and procedures
  - Materials and craftsmanship details
  - Designer background and signature techniques

- **Elegant Personality**: Professional yet warm, sophisticated yet approachable
- **Beautiful Web Interface**: Modern, responsive chat interface with XBL branding
- **Conversation Memory**: Maintains context throughout conversations
- **24/7 Availability**: Never sleeps, always ready to help customers

## Architecture

```
joy/
├── config/
│   ├── xtrabrides_knowledge.json    # Complete business knowledge base
│   └── princess_persona.json        # Princess's personality & behavior
├── app/
│   └── princess_brain.py            # AI logic and OpenAI integration
├── princess_app.py                  # FastAPI web application
├── start_princess.sh                # Startup script
└── requirements.txt                 # Python dependencies
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- OpenAI API key
- Internet connection

### Installation

1. **Navigate to the joy directory**:
   ```bash
   cd /Users/pro/Downloads/ai_receptionist/joy
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Make sure your `.env` file has:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   PRINCESS_PORT=8001
   ```

### Running Locally

**Option 1: Using the startup script**:
```bash
./start_princess.sh
```

**Option 2: Using Python directly**:
```bash
python3 princess_app.py
```

**Option 3: Using Uvicorn**:
```bash
uvicorn princess_app:app --host 0.0.0.0 --port 8001 --reload
```

Princess will be available at:
- Local: http://localhost:8001
- Network: http://0.0.0.0:8001

## Deployment Options

### 1. Deploy to Render.com (Recommended - Free Tier Available)

1. **Create a Render account** at https://render.com

2. **Create a new Web Service**:
   - Connect your GitHub repository (or use the Render dashboard)
   - Root Directory: `joy`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn princess_app:app --host 0.0.0.0 --port $PORT`

3. **Add environment variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `PRINCESS_PORT`: 8001 (optional)

4. **Deploy**: Render will automatically deploy and give you a public URL like:
   `https://princess-xbl.onrender.com`

### 2. Deploy to Railway.app

1. **Create a Railway account** at https://railway.app

2. **New Project** → **Deploy from GitHub**

3. **Configure**:
   - Root Directory: `joy`
   - Start Command: `uvicorn princess_app:app --host 0.0.0.0 --port $PORT`

4. **Add environment variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key

5. Public URL will be automatically generated

### 3. Deploy to Heroku

1. **Install Heroku CLI** and login

2. **Create a `Procfile` in the joy directory**:
   ```
   web: uvicorn princess_app:app --host 0.0.0.0 --port $PORT
   ```

3. **Deploy**:
   ```bash
   heroku create princess-xtrabrides
   heroku config:set OPENAI_API_KEY=your_key_here
   git push heroku main
   ```

### 4. Deploy to DigitalOcean App Platform

1. **Create a DigitalOcean account**

2. **Create a new App**

3. **Connect repository** and configure:
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `uvicorn princess_app:app --host 0.0.0.0 --port 8080`

4. **Add environment variables**:
   - `OPENAI_API_KEY`

### 5. Deploy to Vercel (Serverless)

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Create `vercel.json`** in joy directory:
   ```json
   {
     "version": 2,
     "builds": [
       {
         "src": "princess_app.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "princess_app.py"
       }
     ]
   }
   ```

3. **Deploy**:
   ```bash
   vercel --prod
   ```

## API Endpoints

### `GET /`
Main chat interface - Beautiful web UI for chatting with Princess

### `POST /chat`
Send messages to Princess
```json
{
  "message": "Tell me about your bridal collections",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Welcome to XtraBrides..."}
  ]
}
```

Response:
```json
{
  "reply": "I'd be delighted to tell you about our exquisite collections..."
}
```

### `GET /health`
Health check endpoint

### `GET /api/info`
Get bot information

## Testing Princess Locally

1. Start the server (see Running Locally above)

2. Open your browser to http://localhost:8001

3. Try these test conversations:
   - "Tell me about your collections"
   - "What are your prices?"
   - "I'm getting married in December, can you help?"
   - "Do you ship internationally?"
   - "Who is the designer?"
   - "Which celebrities have you dressed?"

## Customization

### Updating Business Knowledge

Edit `config/xtrabrides_knowledge.json` to update:
- Pricing
- Collections
- Contact information
- Policies
- FAQs

### Updating Princess's Personality

Edit `config/princess_persona.json` to adjust:
- Communication style
- Tone and formality
- Greeting variants
- Response rules

### Changing the UI

The chat interface is embedded in `princess_app.py` in the HTML response. You can customize:
- Colors (currently pink/purple gradient)
- Fonts
- Layout
- Branding elements

## Production Considerations

### Security
- Never commit your `.env` file with real API keys
- Use environment variables on your hosting platform
- Consider rate limiting for production

### Performance
- The app uses `gpt-4o-mini` for fast, cost-effective responses
- Conversation history is limited to last 15 messages to manage token usage
- Consider caching for frequently asked questions

### Monitoring
- Check logs for errors: `tail -f logs/princess.log`
- Monitor OpenAI API usage in your OpenAI dashboard
- Set up uptime monitoring (UptimeRobot, Pingdom, etc.)

## Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
pip install -r requirements.txt
```

### "OpenAI API key not found"
Make sure your `.env` file contains:
```
OPENAI_API_KEY=sk-...
```

### Port already in use
Change the port:
```bash
export PRINCESS_PORT=8002
python3 princess_app.py
```

### Princess giving wrong information
Update the knowledge base in `config/xtrabrides_knowledge.json` and restart the server.

## Support

For technical support with Princess:
- GitHub Issues: [Your repo]
- Email: dev@yourcompany.com

For XtraBrides of Lagos business inquiries:
- Phone: +234 810 618 0911
- Email: xtrabrideslagos@yahoo.com
- Website: xtrabrideslagos.com

## License

© 2026 XtraBrides of Lagos. All rights reserved.

---

**Built with ❤️ using FastAPI, OpenAI GPT-4, and luxury bridal couture knowledge**
