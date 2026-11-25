# 🚀 QUICK START - AI CLOSER VOICE INTEGRATION

## Step 1: Add Your ElevenLabs API Key (2 minutes)

```bash
# Edit the .env file
nano /Users/pro/Downloads/ai_receptionist/joy/.env

# Add this line (replace with your actual key):
ELEVENLABS_API_KEY=your_elevenlabs_api_key_from_closer_studio
```

**Where to find it:**
- ElevenLabs Dashboard: https://elevenlabs.io/app/settings/api-keys
- Or check your Closer Studio config

---

## Step 2: Install New Dependencies (1 minute)

```bash
cd /Users/pro/Downloads/ai_receptionist/joy
source venv/bin/activate  # If using venv
pip install elevenlabs==0.2.26
```

---

## Step 3: Test Locally (5 minutes)

```bash
# Start Joy
python main.py

# Or with uvicorn
uvicorn main:app --reload --port 8000
```

**Then open:** http://localhost:8000/voice/builder

---

## Step 4: Deploy to Production (5 minutes)

```bash
# Upload to your server
cd /Users/pro/Downloads/ai_receptionist/joy

scp -i ~/Downloads/joy.pem -r core ubuntu@13.60.238.119:/opt/joy/
scp -i ~/Downloads/joy.pem app/voice_enhanced.py ubuntu@13.60.238.119:/opt/joy/app/
scp -i ~/Downloads/joy.pem templates/voice/builder.html ubuntu@13.60.238.119:/opt/joy/templates/voice/
scp -i ~/Downloads/joy.pem main.py ubuntu@13.60.238.119:/opt/joy/
scp -i ~/Downloads/joy.pem .env ubuntu@13.60.238.119:/opt/joy/

# SSH into server
ssh -i ~/Downloads/joy.pem ubuntu@13.60.238.119

# Install dependencies & restart
cd /opt/joy
source venv/bin/activate
pip install elevenlabs==0.2.26
sudo systemctl restart joy
```

**Access:** https://joy.aicloser.tech/voice/builder

---

## What Users See

1. **Voice Builder UI** at `https://joy.aicloser.tech/voice/builder`
   - Choose engine (OpenAI or ElevenLabs)
   - Configure assistant
   - Test with microphone
   - Get deployment link

2. **WebSocket Endpoints**
   - OpenAI: `wss://joy.aicloser.tech/voice/enhanced/ws?engine=openai`
   - ElevenLabs: `wss://joy.aicloser.tech/voice/enhanced/ws?engine=elevenlabs`

3. **Integration in Existing Flows**
   - Bot builder now supports voice
   - Demo bots can have voice enabled
   - Customer portal shows voice controls

---

## Test Scenarios

### Test 1: OpenAI Realtime
```
1. Go to https://joy.aicloser.tech/voice/builder
2. Click "OpenAI Realtime"
3. Fill in: Name="Test Bot", Business="Test Hotel"
4. Click "Create Voice Assistant"
5. Click microphone
6. Say: "I need a room for Friday"
7. Listen to response
```

### Test 2: ElevenLabs
```
Same as above, but select "ElevenLabs AI" in step 2
(Requires ELEVENLABS_API_KEY set)
```

---

## Pricing for Your Customers

Charge your users based on engine + usage:

**Starter ($99/month)**
- 500 voice minutes
- OpenAI Realtime Mini
- Your cost: ~$10 → Profit: $89

**Professional ($299/month)**
- 2000 voice minutes  
- OpenAI or ElevenLabs
- Your cost: ~$40-180 → Profit: $119-259

**Premium ($499/month)**
- 5000 voice minutes
- ElevenLabs + custom voice
- Your cost: ~$450 → Profit: $49 (luxury positioning)

---

## URLs

- **Builder:** https://joy.aicloser.tech/voice/builder
- **Existing Voice:** https://joy.aicloser.tech/voice
- **Admin:** https://joy.aicloser.tech/admin
- **Portal:** https://joy.aicloser.tech/portal

---

## Files Changed

```
joy/
├── .env                         ← Added ELEVENLABS_API_KEY
├── main.py                      ← Added voice routes
├── requirements.txt             ← Added elevenlabs
├── core/                        ← NEW FOLDER
│   ├── engines/
│   │   ├── base_engine.py
│   │   ├── openai_realtime.py
│   │   └── elevenlabs_agent.py
│   ├── business_brain/
│   │   └── knowledge_base.py
│   └── actions/
│       └── booking.py
├── app/
│   └── voice_enhanced.py        ← NEW FILE
└── templates/voice/
    └── builder.html             ← NEW FILE
```

---

## Next Actions

1. ✅ Add ELEVENLABS_API_KEY to .env
2. ✅ Test locally
3. ✅ Deploy to production
4. 🚀 Launch to your users!

---

**That's it! Your platform now has real-time voice AI! 🎉**
