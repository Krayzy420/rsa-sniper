import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- CONFIGURATION ---
set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"
FORCE_TEST = True 

# --- THE VERIFIED TARGET LIST ---
VERIFIED_DATA = {
    "WTO": {"ratio": 5, "effective": "2026-02-17", "cutoff": "2026-02-13"}, 
    "ANY": {"ratio": 10, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "ATPC": {"ratio": 50, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "HERZ": {"ratio": 10, "effective": "2026-02-09", "cutoff": "2026-02-06"}
}

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def check_for_last_minute_cil(ticker):
    """Scans for new amendments that might switch Roundup to Cash."""
    try:
        company = Company(ticker)
        latest_filings = company.get_filings(form=["8-K", "8-K/A"]).latest(3)
        for f in latest_filings:
            text = f.text().lower()
            if "cash in lieu" in text or "cash instead" in text:
                return True 
        return False
    except: return False

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price
        return float(price) if price else 0.0
    except: return 0.0

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"   -> Telegram Fail: {e}", flush=True)

def run_rsa_sniper():
    print("SYSTEM ONLINE: Starting Sentry Scan...", flush=True)
    now = datetime.now()
    # Mountain Time adjustment (approximate)
    mountain_hour = (now.hour - 7) % 24 

    seen_filings = load_seen_filings()
    
    for ticker, info in VERIFIED_DATA.items():
        print(f"Checking {ticker}...", flush=True)
        price = get_live_price(ticker)
        cutoff_date = datetime.strptime(info["cutoff"], "%Y-%m-%d").date()
        
        # --- 1. NIGHT CHECK (11 PM MST) ---
        if now.date() == cutoff_date and mountain_hour == 23:
             if price > (get_live_price(ticker) * 1.5):
                 send_telegram_msg(f"✅ NIGHT CONFIRMATION: {ticker} split is processing at ${price:.2f}.")

        # --- 2. CIL ABORT CHECK ---
        if now.date() == cutoff_date:
            if check_for_last_minute_cil(ticker):
                send_telegram_msg(f"🛑 ABORT: {ticker} switched to CASH IN LIEU. Get out now.")
                continue

        # --- 3. STATUS & MATH LOGIC ---
        if now.date() > cutoff_date:
            # POST-SPLIT (Held)
            # If price is < $5.00, it means it hasn't updated for the weekend yet.
            if price < 5.00:
                status = "✅ SPLIT HELD (PENDING UPDATE)"
                estimated_new_price = price * info["ratio"]
                profit = estimated_new_price - price
                price_display = f"${price:.2f} -> ~${estimated_new_price:.2f} (Est. Open)"
                profit_label = "ESTIMATED GAIN"
            else:
                status = "✅ SPLIT CONFIRMED / HELD"
                profit = price - (price / info["ratio"])
                price_display = f"${price:.2f}"
                profit_label = "REALIZED GAIN"
        
        elif now.date() == cutoff_date:
            # CUTOFF DAY
            status = "🚨 CUTOFF TODAY (VERIFIED ROUNDUP)"
            profit = (price * info["ratio"]) - price
            price_display = f"${price:.2f}"
            profit_label = "PROJECTED PROFIT"
            
        else:
            # ACTIVE
            status = "🟢 ACTIVE"
            profit = (price * info["ratio"]) - price
            price_display = f"${price:.2f}"
            profit_label = "PROJECTED PROFIT"

        # --- DUPLICATE GUARD ---
        alert_id = f"{ticker}_{status}_{now.strftime('%Y-%m-%d')}"
        
        if not FORCE_TEST and alert_id in seen_filings:
            print(f"   -> Skipped {ticker} (Already sent today)", flush=True)
            continue 

        msg = (
            f"{status}: {ticker}\n"
            f"-------------------------\n"
            f"💰 {profit_label}: ${profit:.2f}\n"
            f"📉 Price: {price_display}\n"
            f"➗ Split: 1-for-{info['ratio']}\n"
            f"⏳ Buy Before: 4PM EST on {info['cutoff']}\n"
            f"🔗 Link: https://www.google.com/finance/quote/{ticker}:NASDAQ"
        )
        
        send_telegram_msg(msg)
        save_seen_filing(alert_id)

    print("SCAN COMPLETE.", flush=True)

if __name__ == "__main__":
    run_rsa_sniper()
