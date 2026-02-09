import os
import requests
import re
import yfinance as yf
from datetime import datetime, timedelta
from edgar import *

# --- CONFIGURATION ---
set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"
FORCE_TEST = True 

# --- PART 1: THE VERIFIED GUARD (Your Current Plays) ---
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

# --- PART 2: THE SCOUT (Finding New Stuff) ---
def analyze_new_filing(filing):
    text = filing.text().lower()
    
    # 1. Check for Reverse Split Language
    if "reverse stock split" not in text and "reverse split" not in text:
        return None

    # 2. Check for "Gold" (Round Up)
    gold_keywords = ["round up", "rounded up", "nearest whole share", "upward adjustment"]
    if not any(k in text for k in gold_keywords):
        return None # No roundup, ignore it

    # 3. Check for "Round Lot" / "Odd Lot" Risks (The AREB Issue)
    risk_label = "✅ STANDARD ROUNDUP"
    if "round lot" in text or "odd lot" in text:
        risk_label = "⚠️ CHECK ROUND LOT RULES (Might need 100 shares)"

    # 4. Extract Ticker
    try:
        ticker = filing.company.tickers[0]
    except:
        ticker = "UNKNOWN"

    return ticker, risk_label, filing.url

def run_rsa_sniper():
    print("SYSTEM ONLINE: Starting Sentry Scan...", flush=True)
    # Market Clock (UTC to Eastern)
    market_now = datetime.now() - timedelta(hours=5)
    seen_filings = load_seen_filings()
    
    # --- PHASE 1: CHECK VERIFIED TARGETS ---
    print("--- PHASE 1: GUARDING TARGETS ---", flush=True)
    for ticker, info in VERIFIED_DATA.items():
        price = get_live_price(ticker)
        cutoff_date = datetime.strptime(info["cutoff"], "%Y-%m-%d").date()
        
        # STATUS LOGIC
        if market_now.date() > cutoff_date:
            # Post-Split
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
        elif market_now.date() == cutoff_date:
            status = "🚨 CUTOFF TODAY (VERIFIED ROUNDUP)"
            profit = (price * info["ratio"]) - price
            price_display = f"${price:.2f}"
            profit_label = "PROJECTED PROFIT"
        else:
            status = "🟢 ACTIVE"
            profit = (price * info["ratio"]) - price
            price_display = f"${price:.2f}"
            profit_label = "PROJECTED PROFIT"

        alert_id = f"{ticker}_{status}_{market_now.strftime('%Y-%m-%d')}"
        if not FORCE_TEST and alert_id in seen_filings:
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

    # --- PHASE 2: HUNTING FOR NEW DEALS ---
    print("--- PHASE 2: HUNTING NEW FILINGS ---", flush=True)
    try:
        # Scan latest 40 filings (8-K and 6-K for foreign stocks)
        latest_filings = get_filings(form=["8-K", "6-K"]).latest(40)
        
        for filing in latest_filings:
            # Check if we've seen this specific document before
            if filing.accession_number in seen_filings:
                continue

            result = analyze_new_filing(filing)
            if result:
                ticker, risk_label, link = result
                
                msg = (
                    f"🆕 NEW POTENTIAL FOUND: {ticker}\n"
                    f"-------------------------\n"
                    f"Risk Level: {risk_label}\n"
                    f"📄 Filing: 8-K/6-K detected\n"
                    f"🔗 Filing Link: {link}\n"
                    f"⚡ ACTION: Check Discord/Filings immediately!"
                )
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)
                
    except Exception as e:
        print(f"Scout Error: {e}", flush=True)

    print("SCAN COMPLETE.", flush=True)

if __name__ == "__main__":
    run_rsa_sniper()
