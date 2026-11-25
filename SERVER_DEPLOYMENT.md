# 🚀 Deploy Princess to Joy Server

## Quick Deploy

Princess has been integrated into the Joy application and is ready to deploy to your server at **13.60.238.119**.

---

## ✅ What Was Integrated

1. **Princess Routes** added to `main.py`:
   - `GET /princess` - Princess chat interface
   - `GET /demo/princess` - Alternative route
   - `POST /princess/chat` - Princess chat API
   - `POST /demo/princess/chat` - Alternative API route

2. **Princess Template** created:
   - `templates/demo/princess_chat.html` - Beautiful XBL-branded chat UI

3. **Princess Brain** already exists:
   - `app/princess_brain.py` - AI logic with complete XBL knowledge
   - `config/xtrabrides_knowledge.json` - Full business data
   - `config/princess_persona.json` - Princess's personality

---

## 🚀 Deploy to Server

### Option 1: Automatic Deployment (Try First)

```bash
cd /Users/pro/Downloads/ai_receptionist/joy
./deploy_to_server.sh
```

This script will:
1. Package all Princess files
2. Upload to server
3. Extract files
4. Restart Joy service
5. Give you the Princess URL

### Option 2: Manual Deployment

If automatic deployment fails (SSH key issues), follow these steps:

#### Step 1: Create Deployment Package
```bash
cd /Users/pro/Downloads/ai_receptionist/joy

# Create tarball
tar -czf princess_deploy.tar.gz \
    main.py \
    app/princess_brain.py \
    config/xtrabrides_knowledge.json \
    config/princess_persona.json \
    templates/demo/princess_chat.html
```

#### Step 2: Upload to Server
```bash
# Using SCP
scp -i AI_Receptionist.pem princess_deploy.tar.gz ubuntu@13.60.238.119:/tmp/

# OR use SFTP, FileZilla, or any file transfer method
```

#### Step 3: SSH into Server and Deploy
```bash
# Connect to server
ssh -i AI_Receptionist.pem ubuntu@13.60.238.119

# Once connected, run:
cd /tmp
tar -xzf princess_deploy.tar.gz -C ~/joy/
cd ~/joy

# Restart Joy service
sudo systemctl restart joy

# OR if Joy is running as a Python process:
pkill -f "python.*main.py"
nohup python3 main.py &
```

#### Step 4: Verify Deployment
```bash
# Check if Joy is running
sudo systemctl status joy

# OR check process
ps aux | grep python
```

---

## 🌐 Your Princess Links

Once deployed, Princess will be available at:

### If you access via IP:
- http://13.60.238.119/princess
- http://13.60.238.119/demo/princess

### If you have Joy on a domain (e.g., joy.aicloser.tech):
- https://joy.aicloser.tech/princess
- https://joy.aicloser.tech/demo/princess

**This is the link you can share with customers!** It works just like Joy's demo bot links.

---

## 🧪 Test Princess

Once deployed, open the URL and try:

1. "Tell me about your bridal collections"
2. "What are your prices for traditional wedding dresses?"
3. "I'm getting married in December, can you help?"
4. "Do you ship internationally?"
5. "Who is the designer?"
6. "Which celebrities have you dressed?"

---

## 📱 Share the Link

Add Princess link to:
- XtraBrides website: "Chat with Princess" button
- WhatsApp status: Share the link
- Instagram bio: Add link
- Facebook page: Pin the link
- Email signature: "Have questions? Chat with Princess →"

---

## 🔧 Troubleshooting

### "Connection refused"
- Check if Joy service is running: `sudo systemctl status joy`
- Restart: `sudo systemctl restart joy`

### "404 Not Found"
- Verify files were deployed: `ls ~/joy/app/princess_brain.py`
- Check main.py has Princess routes: `grep "princess" ~/joy/main.py`

### "500 Internal Server Error"
- Check Joy logs: `sudo journalctl -u joy -n 50`
- Verify OpenAI API key is set in .env file

### SSH Key Issues
- Fix permissions: `chmod 400 AI_Receptionist.pem`
- Try manual deployment (Option 2)

---

## 🔑 Important Files on Server

After deployment, these files should exist:
```
~/joy/
├── main.py                              (Updated with Princess routes)
├── app/
│   └── princess_brain.py                (Princess AI logic)
├── config/
│   ├── xtrabrides_knowledge.json        (Business knowledge)
│   └── princess_persona.json            (Personality)
└── templates/
    └── demo/
        └── princess_chat.html           (Chat interface)
```

---

## 💡 What Princess Knows

Princess has complete knowledge of:
- All XBL collections (Alora, Hazel, Serene, August, Elegante, Sephora, Madame President, etc.)
- Complete pricing (₦350,000 - ₦15,000,000+)
- Contact info, policies, shipping, FAQs
- Designer background (Oyetomiwa Elizabeth Daniel)
- Celebrity clientele (Davido, Tiwa Savage, etc.)

---

## 📞 Support

### If Deployment Fails:
- Check server access: Can you SSH into 13.60.238.119?
- Verify Joy is running on the server
- Check .env file has OPENAI_API_KEY

### Contact Info in Princess:
- Phone: +234 810 618 0911
- Email: xtrabrideslagos@yahoo.com
- Website: xtrabrideslagos.com

---

## 🎯 Next Steps

1. **Run deployment script**: `./deploy_to_server.sh`
2. **Get your URL**: `http://13.60.238.119/princess` (or your domain)
3. **Test Princess**: Visit the URL and chat
4. **Share the link**: Add to website, social media, WhatsApp

---

**🎉 Princess will be live at: http://13.60.238.119/princess**

Just deploy and share the link! ✨
