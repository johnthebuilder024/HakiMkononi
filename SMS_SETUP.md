# HakiMkononi — Africa's Talking SMS Bot Setup Guide

SMS reaches every Kenyan phone — smartphone, feature phone, even a Nokia 3310.
No WhatsApp needed. No internet needed on Wanjiku's side.

---

## How It Works

```
Wanjiku texts: "Nilifukuzwa kazi bila notisi"
      ↓  to your short code
HakiMkononi reads the law (RAG + Groq AI)
      ↓
Wanjiku receives 3-4 SMS with the legal answer
```

---

## Step 1 — Create a free Africa's Talking account

1. Go to **https://account.africastalking.com/auth/register**
2. Sign up — it's completely free
3. Verify your email

---

## Step 2 — Get your Sandbox API Key

1. Log in to the AT dashboard
2. Click **Sandbox** (top of page — make sure you're in sandbox mode)
3. Go to **Settings → API Key**
4. Copy your API key

5. Open your `.env` file and update:
```
AT_USERNAME=sandbox
AT_API_KEY=your-actual-api-key-here
AT_SENDER_ID=
```

---

## Step 3 — Create a Sandbox SMS Short Code

1. In the AT dashboard (sandbox mode), go to **SMS → Short Codes**
2. Click **Create Short Code**
3. Set the **callback URL** (webhook) to:
   ```
   https://margin-comma-showgirl.ngrok-free.dev/api/sms/
   ```
   (replace with your current ngrok URL)
4. Note down your short code (e.g. `15629`)

---

## Step 4 — Start your servers

**Terminal 1 — Django:**
```powershell
python manage.py runserver --noreload
```

**Terminal 2 — ngrok (if not already running):**
```powershell
.\ngrok.exe http 8000
```
Copy the `https://xxxxx.ngrok-free.app` URL and update the AT callback above.

---

## Step 5 — Test using the AT Simulator

The AT sandbox doesn't send real SMS to phones — it uses a web simulator.

1. Go to **https://simulator.africastalking.com:1517/**
2. Log in with your AT sandbox credentials
3. At the top, enter your short code
4. Click **SMS** tab
5. In the simulator, type messages as if you're Wanjiku:

```
You type: hi
Bot replies: HAKIMKONONI: Karibu! Chagua lugha / Choose language:
             1=Kiswahili 2=English 3=Sheng

You type: 2
Bot replies: HAKIMKONONI: Great! Language: English. Now text me your legal problem.

You type: My boss fired me without notice, what are my rights?
Bot replies: HAKIMKONONI: Reading the law... answer coming in ~1 minute.
             (then 3-4 more SMS with the full answer)
```

---

## Step 6 — Test with a real phone (going live)

To send real SMS to real Kenyan phones:

1. In the AT dashboard, switch from **Sandbox** to **Live**
2. Add credit to your wallet (minimum KSh 10 / ~$0.08)
3. Update `.env`:
   ```
   AT_USERNAME=your-actual-at-username
   AT_API_KEY=your-live-api-key
   ```
4. Register a proper short code or sender ID with AT
5. SMS cost: ~KSh 0.8 per message sent to Wanjiku

---

## SMS Format

Each answer comes as numbered SMS parts:

```
1/4 HAKIMKONONI: | LAW: Under Employment Act 2007 S.35, you are entitled 
    to notice of termination...

2/4 YOUR RIGHTS: You were not given proper notice. Your employer must pay 
    wages in lieu of notice...

3/4 Ref: Section 35, Section 38 | Legal info only, not advice.
```

---

## USSD (coming next)

USSD works with zero internet — just a GSM signal.
Wanjiku dials `*384*XXXX#` and gets a menu.
Works even on a 2G feature phone.
Completely free for Wanjiku (no SMS cost, no data cost).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| SSL error in logs | Normal in local test — AT sandbox needs real internet from a server |
| No response in simulator | Check ngrok is running and callback URL is correct in AT dashboard |
| `AT_USERNAME or AT_API_KEY not set` | Check .env file has correct values |
| Messages not arriving | Make sure you're testing in simulator, not real phone (sandbox only) |

---

*Built for Wanjiku — every Kenyan deserves to know their rights 🇰🇪*
