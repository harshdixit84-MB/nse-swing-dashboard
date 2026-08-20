# NSE Swing Dashboard

Fully automated EMA-Pullback swing trade scanner for NSE stocks, with a live web
dashboard and Telegram alerts.

## How it works

```
GitHub Actions (runs daily, after NSE close)
   -> scanner/scan.py
      -> fetches NSE stock universe
      -> pulls daily OHLCV data (yfinance)
      -> applies the EMA Pullback strategy
      -> writes data/candidates.json + data/history.json
      -> sends a Telegram alert for any NEW setup
   -> commits the updated data/*.json back to the repo

Vercel-hosted dashboard (dashboard/)
   -> fetches data/candidates.json directly from GitHub (raw content)
   -> renders it as a live table -- no rebuild/redeploy needed when data updates
```

Because the dashboard reads data straight from GitHub's raw content URL, new scan
results appear on the site within seconds of the Action committing them --
you don't need to redeploy on Vercel each day.

## Strategy implemented

Trend Pullback to 20/50 EMA:
- Stock in an uptrend: close > EMA20 > EMA50, close > EMA50
- Pullback of 5-15% from the 20-bar swing high
- Price within 2% of the 20 or 50 EMA
- Bullish reversal candle (hammer or bullish engulfing) on the signal day
- Reversal-day volume >= 20-day average volume
- Liquidity filter: 20-day average volume >= 500,000 shares
- Stop-loss: tighter of (5-bar pullback low, 50 EMA), minus 0.5% buffer
- Target: higher of (2x risk) or (prior 20-bar swing high)

All thresholds are adjustable in `scanner/config.py`.

## Setup (step by step)

### 1. Create the GitHub repo
Push this folder to a new GitHub repo (e.g. `nse-swing-dashboard`).

### 2. Add GitHub Secrets
In the repo: Settings -> Secrets and variables -> Actions -> New repository secret.
Add:
- `TELEGRAM_BOT_TOKEN` -- from @BotFather on Telegram
- `TELEGRAM_CHAT_ID` -- your personal or group chat ID

### 3. Enable the workflow
The workflow at `.github/workflows/daily-scan.yml` runs automatically on a daily
cron schedule (weekdays, after 3:30 PM IST close). You can also trigger it
manually from the Actions tab ("Run workflow") to test it immediately.

### 4. Deploy the dashboard to Vercel
- Go to vercel.com -> New Project -> import this GitHub repo
- Set the project's **Root Directory** to `dashboard`
- In `dashboard/pages/index.js`, replace `YOUR_GITHUB_USERNAME/YOUR_REPO_NAME`
  with your actual GitHub username and repo name (two places)
- Deploy

That's it -- the scanner runs daily and commits results, and the dashboard
always shows the latest `data/candidates.json` straight from GitHub.

## Local testing (optional)

```bash
cd scanner
pip install -r requirements.txt
python scan.py
```

This writes `data/candidates.json` and `data/history.json` locally so you can
check the output before relying on the scheduled Action.

## Files

| Path | Purpose |
|---|---|
| `scanner/config.py` | All strategy thresholds in one place |
| `scanner/universe.py` | Fetches the NSE stock list (with a local fallback) |
| `scanner/strategy.py` | The EMA Pullback detection logic |
| `scanner/scan.py` | Orchestrates the daily run |
| `scanner/telegram_alert.py` | Sends Telegram messages for new setups |
| `.github/workflows/daily-scan.yml` | Daily cron job |
| `dashboard/` | Next.js dashboard, deployed on Vercel |
| `data/candidates.json` | Today's setups (auto-generated) |
| `data/history.json` | Every setup ever found, for a track record |
