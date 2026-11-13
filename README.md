# ⚡ Free XAUUSD SMC Cloud Alert System ⚡

A 100% free, production-grade cloud alert system that monitors **XAUUSD (Gold) on the 5-minute (M5) timeframe** for **Smart Money Concepts (SMC)** structure breaks:
- **Bullish & Bearish CHOCH** (Change of Character)
- **Bullish & Bearish MSS** (Market Structure Shift)
- Instant alerts delivered directly to your **Telegram** on mobile/desktop.
- **₹0 Budget**: Powered by Python, legitimate free market data feeds, and scheduled automated GitHub Actions.
- **Zero local computer uptime required**: Runs completely in the cloud. Your laptop can stay turned off.

---

## 🏛️ System Architecture

```
  ┌─────────────────────────────────────────────────────────┐
  │                 GITHUB ACTIONS (Cloud)                  │
  │                  Scheduled Cron (*/5m)                  │
  └────────────────────────────┬────────────────────────────┘
                               │
            ┌──────────────────▼──────────────────┐
            │  1. DATA PROVIDER ENGINE            │
            │     - Primary: Yahoo Spot XAUUSD=X  │
            │     - Fallback: COMEX Futures GC=F  │
            │     - Alternate: Twelve Data API    │
            └──────────────────┬──────────────────┘
                               │ (Strictly Completed M5 Candles)
            ┌──────────────────▼──────────────────┐
            │  2. SMC QUANTITATIVE DETECTOR       │
            │     - Zero Repainting Pivots        │
            │     - Trend State (HH/HL vs LH/LL)  │
            │     - CHOCH & MSS Classification    │
            │     - Candle-Close Confirmation     │
            │     - ATR Displacement Filter       │
            └──────────────────┬──────────────────┘
                               │ (New Confirmed Breaks)
            ┌──────────────────▼──────────────────┐
            │  3. DEDUPLICATION & STATE ENGINE    │
            │     - Cross-Run Persistent Cache    │
            │     - Single Alert Per Unique Break │
            └──────────────────┬──────────────────┘
                               │
            ┌──────────────────▼──────────────────┐
            │  4. TELEGRAM BOT API DISPATCHER     │
            │     - Clean Rich HTML Mobile Alert  │
            │     - IST Timestamps & Break Level  │
            │     - Full Structural Context       │
            └─────────────────────────────────────┘
```

---

## 📊 Market Data Feeds & Price Disclosures

### Gold Spot (CFD) vs Gold Futures (`GC=F`)
Retail brokers like **Funded Trader Markets (FTM)** price **XAUUSD** as an OTC spot contract based on London OTC spot gold interbank pricing.
- **Primary Feed (`XAUUSD=X`)**: Tracks global Spot Gold in USD per troy ounce. This closely aligns with broker CFD pricing.
- **Fallback Feed (`GC=F`)**: COMEX Gold Futures. Futures prices reflect contract delivery dates and carry contango or backwardation (typically a \$5 to \$30 difference from spot). The system will alert you if the fallback is ever active so you are fully aware of any basis difference.
- **Twelve Data (`XAU/USD`)**: Supported as an alternate option via free tier API key (800 free credits/day).

---

## 🧠 SMC Detection Engine & Precise Definitions

Unlike subjective chart drawing, this system implements **unambiguous, rule-based algorithmic definitions**:

### 1. Swing Point Identification (Fractal Lookback)
- **Swing High**: A candle high strictly greater than $N$ candles before and $N$ candles after (default: $N=3$ bars, configurable).
- **Swing Low**: A candle low strictly less than $N$ candles before and $N$ candles after.
- **Zero Repainting Guarantee**: A swing at candle $i$ is only registered after candle $i + N$ has closed. Unclosed live candles are completely excluded from structure registration.

### 2. Trend State Tracking
- **Bullish Trend**: Sequence of confirmed Higher Highs (HH) and Higher Lows (HL).
- **Bearish Trend**: Sequence of confirmed Lower Lows (LL) and Lower Highs (LH).

### 3. CHOCH (Change of Character) — Trend Reversal
- **Bullish CHOCH**: In an established **Bearish trend** (forming LL and LH), price breaks and **closes above the key Lower High (LH)** that led to the lowest low. This signals the earliest potential macro reversal from bearish to bullish.
- **Bearish CHOCH**: In an established **Bullish trend** (forming HH and HL), price breaks and **closes below the key Higher Low (HL)** that led to the highest high. This signals the earliest potential macro reversal from bullish to bearish.

### 4. MSS (Market Structure Shift) — Institutional Displacement
- **Bullish MSS**: Price decisively breaks above a key confirmed Swing High accompanied by **strong displacement**:
  - Breakout candle body/range $\ge 1.0 \times \text{ATR}(14)$
  - Candle close is strongly bullish (`close > open`) and closes above the break level.
- **Bearish MSS**: Price decisively breaks below a key confirmed Swing Low accompanied by **strong displacement**:
  - Breakout candle body/range $\ge 1.0 \times \text{ATR}(14)$
  - Candle close is strongly bearish (`close < open`) and closes below the break level.

### 5. Candle-Close Confirmation
A wick poking beyond a level is considered a liquidity sweep or rejection. An alert is **only** triggered when the candle **closes** beyond the break level (unless `CONFIRMATION_MODE=wick` is configured).

---

## 📱 Telegram Alert Preview

Whenever a confirmed break occurs on a newly closed M5 candle, you receive an alert like this on your mobile:

```
⚡ XAUUSD | M5 Structure Alert ⚡

Signal: 🟢 Bullish MSS
Break Level: 2735.50
Close Price: 2737.10
Time: 13-Nov-2026 06:35 PM IST
Status: Confirmed candle close
Displacement: 1.45x ATR
Session: London / New York Overlap
Data Provider: Yahoo Finance (XAUUSD=X)

📖 Context:
Impulsive bullish candle broke above swing high (2735.50) with 1.45x ATR displacement, confirming a Bullish Market Structure Shift (MSS).

⚠️ Alert & chart analysis only. Never risk capital without independent confirmation.
```

---

## 🚀 Quick Setup Guide (Step-by-Step)

### Step 1: Create your Free Telegram Bot (2 minutes)
1. Open Telegram and search for [`@BotFather`](https://t.me/botfather).
2. Send `/newbot`.
3. Give your bot a name (e.g. `MyGoldSMCAlerts`) and a username ending in `bot` (e.g. `MyGoldSMC_bot`).
4. `@BotFather` will give you a **HTTP API Token** (e.g. `7123456789:ABCdef-GhIjkLmNoPqRsTuVwXyZ`). **Save this.**
5. Now start your new bot by opening its chat and pressing **Start**.
6. Find your numerical **Chat ID**:
   - Search Telegram for [`@userinfobot`](https://t.me/userinfobot) and press **Start**. It will immediately reply with your `Id` (e.g. `987654321`). **Save this.**

### Step 2: Test Locally (Optional)
If you wish to test on your laptop:
```bash
# Clone or open this folder
cd XAUUSD_SMC_Alert_System

# Create virtual environment and install packages
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run Unit Tests
pytest -v

# Run Health Check (no telegram credentials required)
python main.py --health-check

# Run Dry-Run (prints alerts without sending)
python main.py --dry-run
```

To test your Telegram connection:
```bash
# In your terminal or in a .env file:
python -c "from telegram_alerts import test_telegram_connection; test_telegram_connection('YOUR_TOKEN', 'YOUR_CHAT_ID')"
```

---

## ☁️ Cloud Deployment via GitHub Actions (Zero Hosting Cost)

You do **NOT** need to keep your laptop on. GitHub will run the system automatically every 5 minutes on their free servers.

### 1. Create a Private GitHub Repository
1. Go to [github.com/new](https://github.com/new).
2. Name your repository (e.g., `xauusd-smc-alerts`).
3. Set visibility to **Private** (to protect your repository).
4. Do NOT initialize with a README (we already have everything prepared).
5. Click **Create repository**.

### 2. Push Code to GitHub
In your project folder, run:
```bash
git init
git add .
git commit -m "Initial commit of XAUUSD SMC Alert System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/xauusd-smc-alerts.git
git push -u origin main
```

### 3. Add GitHub Secrets
To protect your Telegram bot credentials:
1. In your GitHub repository, click **Settings** (top tab).
2. In the left sidebar, click **Secrets and variables** > **Actions**.
3. Click the green button **New repository secret**.
4. Add the following secrets:

| Secret Name | Description | Example Value |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token from @BotFather | `7123456789:ABCdef-GhIjkLm...` |
| `TELEGRAM_CHAT_ID` | Your numerical Chat ID from @userinfobot | `987654321` |
| `TWELVEDATA_API_KEY` | *(Optional)* If using TwelveData | *(Leave empty if using Yahoo)* |

### 4. Enable & Test the Workflow
1. Go to the **Actions** tab in your repository.
2. Select **XAUUSD SMC Alert Monitor** from the left list.
3. Click **Run workflow** > select `dry_run = false` > click green **Run workflow** button.
4. Watch the run complete with a green checkmark!

---

## ⚙️ Configuration Reference

All settings can be adjusted via environment variables in GitHub Secrets or `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `DATA_PROVIDER` | `yahoo` | `yahoo` (free) or `twelvedata` |
| `YAHOO_SYMBOL` | `XAUUSD=X` | Spot Gold feed symbol |
| `SWING_LENGTH` | `3` | Pivot lookback bars on each side for fractal swings |
| `MIN_DISPLACEMENT_ATR_MULT` | `1.0` | Minimum ATR displacement ratio required for MSS |
| `ATR_PERIOD` | `14` | Lookback period for ATR volatility |
| `CONFIRMATION_MODE` | `close` | `close` (candle close) or `wick` |
| `FILTER_SESSIONS` | `false` | `true` restricts alerts to London/NY sessions; `false` monitors 24/5 |
| `ALERT_TIMEZONE` | `Asia/Kolkata` | Timezone for alert timestamps (IST) |
| `DRY_RUN` | `false` | Print alerts to logs without broadcasting to Telegram |

---

## ⚠️ Known Limitations & Responsible Disclosures

1. **GitHub Actions Scheduling Jitter**:
   GitHub free-tier scheduled cron jobs run on shared queue infrastructure. During global peak load times, execution may experience delays of 1 to 10 minutes. The system is designed to handle this gracefully by fetching the full recent historical window and deduplicating by candle timestamp.
2. **Alert & Analysis Purpose Only**:
   This tool is built strictly for **chart structure notifications**. It never places trades, never connects to broker execution credentials, and never touches your trading capital.
3. **No Trading Advice**:
   Market Structure Shifts and Changes of Character are structural indicators, not guaranteed profitable trade signals. Always conduct your own risk management and confluence analysis before making trading decisions.
