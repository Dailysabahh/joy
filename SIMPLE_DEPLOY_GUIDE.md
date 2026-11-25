# 🚀 PRINCESS DEPLOYMENT - SIMPLE GUIDE

## ✅ Princess is Ready!

Princess has been integrated into Joy. You just need to upload 5 files to your server.

---

## 📦 Files to Upload

Upload these files from `/Users/pro/Downloads/ai_receptionist/joy/` to your server:

### 1. Main Application (UPDATED)
```
main.py  →  /home/ubuntu/joy/main.py
```
**Important:** This file now includes Princess routes

### 2. Princess Brain
```
app/princess_brain.py  →  /home/ubuntu/joy/app/princess_brain.py
```

### 3. Knowledge Base
```
config/xtrabrides_knowledge.json  →  /home/ubuntu/joy/config/xtrabrides_knowledge.json
config/princess_persona.json      →  /home/ubuntu/joy/config/princess_persona.json
```

### 4. Chat Template
```
templates/demo/princess_chat.html  →  /home/ubuntu/joy/templates/demo/princess_chat.html
```

---

## 🔧 How to Upload

### Option 1: Using FileZilla (Easiest)

1. Download FileZilla: https://filezilla-project.org
2. Open FileZilla
3. Go to: File → Site Manager → New Site
4. Settings:
   - Protocol: SFTP
   - Host: 13.60.238.119
   - Port: 22
   - Logon Type: Key file
   - User: ubuntu
   - Key file: `/Users/pro/Downloads/ai_receptionist/AI_Receptionist.pem`
5. Click "Connect"
6. Upload the 5 files to the correct locations

### Option 2: Using Terminal (Mac/Linux)

Fix SSH key permissions first:
```bash
chmod 600 /Users/pro/Downloads/ai_receptionist/AI_Receptionist.pem
```

Then upload each file:
```bash
cd /Users/pro/Downloads/ai_receptionist/joy

# Upload main.py
scp -i ../AI_Receptionist.pem main.py ubuntu@13.60.238.119:/home/ubuntu/joy/

# Upload princess_brain.py
scp -i ../AI_Receptionist.pem app/princess_brain.py ubuntu@13.60.238.119:/home/ubuntu/joy/app/

# Upload knowledge files
scp -i ../AI_Receptionist.pem config/xtrabrides_knowledge.json ubuntu@13.60.238.119:/home/ubuntu/joy/config/
scp -i ../AI_Receptionist.pem config/princess_persona.json ubuntu@13.60.238.119:/home/ubuntu/joy/config/

# Upload template
scp -i ../AI_Receptionist.pem templates/demo/princess_chat.html ubuntu@13.60.238.119:/home/ubuntu/joy/templates/demo/
```

### Option 3: Using WinSCP (Windows)

1. Download WinSCP: https://winscp.net
2. New Session:
   - Protocol: SFTP
   - Host: 13.60.238.119
   - User: ubuntu
   - Private key: AI_Receptionist.pem
3. Connect and drag-drop the 5 files

---

## 🔄 Restart Joy Service

After uploading files, restart Joy:

### Method 1: SSH and Restart
```bash
ssh -i /Users/pro/Downloads/ai_receptionist/AI_Receptionist.pem ubuntu@13.60.238.119

# Once connected:
sudo systemctl restart joy
```

### Method 2: If Joy runs as Python process
```bash
ssh -i /Users/pro/Downloads/ai_receptionist/AI_Receptionist.pem ubuntu@13.60.238.119

# Once connected:
pkill -f "python.*main.py"
cd ~/joy
nohup python3 main.py &
```

---

## 🌐 Your Princess Link

After deployment and restart, Princess will be live at:

### Main Links:
- **http://13.60.238.119/princess**
- **http://13.60.238.119/demo/princess**

### If Joy is on a domain (e.g., joy.aicloser.tech):
- **https://joy.aicloser.tech/princess**
- **https://joy.aicloser.tech/demo/princess**

---

## 🧪 Test Princess

Open the link and ask:
1. "Tell me about your bridal collections"
2. "What are your prices?"
3. "Do you ship internationally?"

---

## 📋 Quick Checklist

- [ ] Upload `main.py`
- [ ] Upload `app/princess_brain.py`
- [ ] Upload `config/xtrabrides_knowledge.json`
- [ ] Upload `config/princess_persona.json`
- [ ] Upload `templates/demo/princess_chat.html`
- [ ] Restart Joy service
- [ ] Test http://13.60.238.119/princess
- [ ] Share link with customers!

---

## 🆘 Troubleshooting

### Can't connect to server?
- Try fixing key permissions: `chmod 600 AI_Receptionist.pem`
- Try FileZilla or WinSCP instead of terminal

### Princess link shows 404?
- Verify files were uploaded to correct locations
- Check Joy logs: `sudo journalctl -u joy -n 50`
- Restart Joy service again

### Princess not responding?
- Check .env file has OPENAI_API_KEY on server
- Check Joy logs for errors

---

## 🎯 Alternative: One-Command Upload (If SSH Works)

If you fix the SSH key permissions, run this:

```bash
cd /Users/pro/Downloads/ai_receptionist/joy

# Fix key permissions
chmod 600 ../AI_Receptionist.pem

# Upload all files at once
rsync -avz -e "ssh -i ../AI_Receptionist.pem" \
  main.py \
  app/princess_brain.py \
  config/xtrabrides_knowledge.json \
  config/princess_persona.json \
  templates/demo/princess_chat.html \
  ubuntu@13.60.238.119:/home/ubuntu/joy/

# Restart Joy
ssh -i ../AI_Receptionist.pem ubuntu@13.60.238.119 "sudo systemctl restart joy"
```

---

**🎉 That's it! Upload 5 files, restart Joy, and Princess is live!**

**Your link: http://13.60.238.119/princess** ✨
