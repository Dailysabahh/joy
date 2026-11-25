# WhatsApp Business API — Complete Setup Guide

This guide walks you through getting Joy live on WhatsApp from zero to fully approved.
Follow every step in order.

---

## Overview

You need three things:
1. A **Meta Business Account** (verified)
2. A **WhatsApp Business API** phone number registered in the Meta Developer console
3. Joy deployed on your server with HTTPS

---

## PART 1 — Deploy Joy to AWS First

You need Joy running on HTTPS before you can configure the webhook in Meta.

### Step 1 — Point a domain at your server

Go to your domain registrar (e.g. Namecheap, GoDaddy) and create an **A record**:

| Type | Name | Value |
|------|------|-------|
| A | joy | 51.20.136.254 |

This creates `joy.closertech.ai` → your server. Wait 5–10 minutes for DNS to propagate.

### Step 2 — Upload Joy to the server

On your Mac, open Terminal:

```bash
# Upload the joy folder
scp -i ~/Downloads/joy.pem -r ~/Downloads/ai_receptionist/joy ubuntu@13.60.238.119:/tmp/joy

# SSH into the server
ssh -i ~/Downloads/joy.pem ubuntu@13.60.238.119
```

### Step 3 — Run the setup script

On the server:

```bash
# Edit the script to set your domain
nano /tmp/joy/deploy/setup.sh
# Change the line: DOMAIN=""
# To:              DOMAIN="joy.closertech.ai"
# Save with Ctrl+O, Enter, Ctrl+X

# Run setup
sudo bash /tmp/joy/deploy/setup.sh
```

### Step 4 — Fill in your credentials

```bash
nano /opt/joy/.env
```

Fill in the values (you'll get the WhatsApp ones in Part 2):

```
OPENAI_API_KEY=sk-...
WHATSAPP_TOKEN=           # Fill after Part 2
WHATSAPP_PHONE_NUMBER_ID= # Fill after Part 2
WHATSAPP_VERIFY_TOKEN=joy_secret_verify_2024
ADMIN_WHATSAPP_NUMBER=2348XXXXXXXXX  # Your WhatsApp number with country code
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourStrongPassword123
SECRET_KEY=SomeLongRandomString
BASE_URL=https://joy.closertech.ai
```

### Step 5 — Start Joy

```bash
sudo systemctl start joy
sudo systemctl status joy  # Should show "active (running)"
```

Test it works:

```bash
curl https://joy.closertech.ai/health
# Should return: {"status": "ok", "service": "Joy — Closer Tech AI Assistant"}
```

---

## PART 2 — WhatsApp Business API Setup

### Step 6 — Create a Meta Business Account

1. Go to [business.facebook.com](https://business.facebook.com)
2. Click **Create Account**
3. Enter your business name: **Closer Tech**
4. Enter your name and business email
5. Complete the setup

### Step 7 — Verify your business

This is required before you can send messages to non-test numbers.

1. In Meta Business Manager, go to **Settings → Business Info**
2. Click **Start Verification**
3. Select your country and business type
4. Enter your business address and phone number
5. You'll be asked to verify via phone call, SMS, or by submitting business documents
6. Upload your business registration document or utility bill with your business name
7. Approval typically takes **1–5 business days**

> While waiting for verification, you can still test with test phone numbers.

### Step 8 — Create a Meta Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps** → **Create App**
3. Select **Business** as the app type
4. App name: **Closer Tech Joy**
5. Select your Business Account: Closer Tech
6. Click **Create App**

### Step 9 — Add WhatsApp to your app

1. On the App dashboard, click **Add Product**
2. Find **WhatsApp** and click **Set Up**
3. You are now on the WhatsApp API Setup page

### Step 10 — Get your Phone Number ID and Token

On the **WhatsApp → API Setup** page:

1. **To (send test messages):** Add your personal WhatsApp number as a test recipient
2. Under **Send and receive messages**, you'll see:
   - **Phone number ID** — copy this, it goes in `.env` as `WHATSAPP_PHONE_NUMBER_ID`
   - **Temporary access token** — copy this for now (valid 24h; you'll generate a permanent one in Step 13)

3. Test it works — click **Send Message** to send a test to yourself

### Step 11 — Configure the Webhook

1. On the left sidebar, click **Configuration** under WhatsApp
2. Click **Edit** next to Webhook
3. **Callback URL:** `https://joy.closertech.ai/webhook`
4. **Verify token:** `joy_secret_verify_2024` *(must match `WHATSAPP_VERIFY_TOKEN` in your .env)*
5. Click **Verify and Save** — Meta will call your webhook to verify it
6. After verification, click **Manage** and enable the **messages** subscription field
7. Click **Done**

> If verification fails: check Joy is running (`sudo systemctl status joy`) and HTTPS is working.

### Step 12 — Register your WhatsApp Business number

You have two options:

**Option A — Use an existing WhatsApp Business number:**
- Your existing WhatsApp Business number must be deleted from the WA Business app first
- Then add it in Meta Business Manager → WhatsApp → Phone Numbers → Add Phone Number

**Option B — Use a new number:**
- Get a new SIM or virtual number
- Add it in Meta Business Manager → WhatsApp → Phone Numbers → Add Phone Number
- Verify via SMS or voice call

### Step 13 — Generate a permanent access token

The temporary token from Step 10 expires in 24 hours. Create a permanent one:

1. In Meta Business Manager, go to **Settings → System Users**
2. Click **Add** → create a system user (e.g. `joy-bot`)
3. Role: **Admin**
4. Click **Generate New Token**
5. Select your **Closer Tech Joy** app
6. Enable permissions: `whatsapp_business_messaging`, `whatsapp_business_management`
7. Click **Generate Token** — copy it immediately (shown only once)
8. Update your server: `sudo nano /opt/joy/.env` → set `WHATSAPP_TOKEN=your_permanent_token`
9. Restart: `sudo systemctl restart joy`

### Step 14 — Update your .env with final values

```bash
ssh -i ~/Downloads/joy.pem ubuntu@13.60.238.119
sudo nano /opt/joy/.env
```

Set:
- `WHATSAPP_TOKEN` = permanent token from Step 13
- `WHATSAPP_PHONE_NUMBER_ID` = Phone Number ID from Step 10

Save, then restart:

```bash
sudo systemctl restart joy
```

---

## PART 3 — Go Live

### Step 15 — Remove test number restriction

By default, you can only send to verified test numbers. To message anyone:

1. Complete **Business Verification** (Step 7 — must be approved)
2. In Meta Business Manager → WhatsApp → Phone Numbers, your number should show **Connected**
3. Once business is verified, you can message any WhatsApp number worldwide

### Step 16 — Test Joy end-to-end

1. Send a WhatsApp message to your business number from any phone
2. Joy should reply within 2–3 seconds
3. Test the full flow: greeting → ask about services → try "build me a demo bot"
4. Check the admin dashboard: `https://joy.closertech.ai/admin`

### Step 17 — Set up 24-hour messaging policy (important)

Meta's policy: you can only send messages to a customer within **24 hours** of their last message.
After 24 hours, you can only send approved **Template Messages**.

For Joy's use case (responding to incoming messages), this is not a problem — Joy only replies when the customer writes first.

---

## PART 4 — Adding a New Customer's WhatsApp Number

When a customer buys a bot and wants Joy running on their number:

### Option A — Separate Meta App per customer (recommended for full isolation)

1. Create a new Meta Developer App (Steps 8–9)
2. Add WhatsApp product
3. Register the customer's phone number (Step 12)
4. Generate a token for this app (Step 13)
5. SSH into the server and update `.env`:
   ```bash
   sudo nano /opt/joy/.env
   # Update WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_TOKEN
   sudo systemctl restart joy
   ```

> For multiple simultaneous customers, you would deploy separate Joy instances on different ports.
> Contact your developer to set up multi-tenant mode.

### Option B — Multiple numbers on the same Meta App

1. In your existing Meta App → WhatsApp → Manage Phone Numbers → Add Phone Number
2. Register the customer's number
3. Note the new **Phone Number ID**
4. Update `.env` with the new `WHATSAPP_PHONE_NUMBER_ID`
5. Restart Joy

---

## Useful Commands

```bash
# SSH into server
ssh -i ~/Downloads/joy.pem ubuntu@13.60.238.119

# Check Joy status
sudo systemctl status joy

# View live logs
sudo journalctl -u joy -f

# Restart Joy (after .env changes)
sudo systemctl restart joy

# Check Nginx
sudo systemctl status nginx
sudo nginx -t

# Renew SSL certificate (auto-renewed, but manual if needed)
sudo certbot renew
```

---

## Admin Dashboard

URL: `https://joy.closertech.ai/admin`
Username and password: set in `.env` as `ADMIN_USERNAME` and `ADMIN_PASSWORD`

The dashboard shows:
- All users Joy has spoken to (with unique IDs and full conversation history)
- All demo bots created (with shareable links)
- All payment leads with customer name, email, and plan selected
- Settings page with phone number swap instructions

---

## Support

If you encounter issues:
- Check logs: `sudo journalctl -u joy -f`
- Verify webhook: Meta Business → WhatsApp → Configuration → test webhook
- Verify SSL: `curl https://joy.closertech.ai/health`
- Check `.env` is complete: `cat /opt/joy/.env`
