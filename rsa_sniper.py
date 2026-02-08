import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- CONFIGURATION ---
FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER:
    FORCE_TEST_TICKER = FORCE_TEST_TICKER.strip().upper()
    # AUTO-CORRECT HERZ -> HTZ
    if FORCE_TEST_TICKER == "HERZ": FORCE_TEST_TICKER = "HTZ"
    if FORCE_TEST_TICKER == "": FORCE_TEST_TICKER = None

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
        
        if price is None or price == 0:
            price = stock.info.get('previousClose', 0.0)
            
        return float(price)
    except:
        return 0.0

def analyze_split_data(text):
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # 1. Remove "Range" language to avoid grabbing the wrong numbers
    # (e.g. "range of 1-for-2 to 1-for-50")
    clean_text = re.sub(r'range of 1-for-[0-9]+ to 1-for-[0-9]+', '', clean_text)

    # 2. Look for definitive 1-for-X
    match = re.search(r'1-for-([0-9]+)', clean_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
    
    # 3. Look for "One-for-Twenty" text variants if number failed
    if ratio == 0:
        if "one-for-twenty" in clean_text: ratio = 20
        elif "one-for-ten" in clean_text: ratio = 10
        elif "one-for-fifty" in clean_text: ratio = 50

    # 4. Date Check
    date_str = "Unknown"
    is_expired = False
    
    # Try to find "Effective [Date]"
    date_match = re.search(r'effective (as of )?([a-z]+ [0-9]{1,2},? [0-9]{4})', clean_text)
    if date_match:
        date_str = date_match.group(2)
        try:
            eff_date_obj = parser.parse(date_str)
            now = datetime.now()
            if eff_date_obj < now: is_expired = True
        except: pass
        
    return ratio, date_str, is_expired

def check_gold_status(text):
    if not text: return "NONE"
    clean_text = re.sub(r'\s+', ' ', text).lower()

    # KILLER PHRASES
    bad_patterns = [r"cash (payment )?in lieu", r"paid in cash", r"rounded down"]
    if any(re.search(p, clean_text) for p in bad_patterns):
        return "BAD"

    # GOLD PHRASES
    good_patterns = [
        r"round(ed|ing)? up",
        r"whole share",
        r"upward adjustment",
        r"nearest whole number",
        r"no fractional shares.*issued"
    ]
    if any(re.search(p, clean_text) for p in good_patterns):
        return "GUARANTEED"

    return "NONE"

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    try: requests.get(url, params=params)
    except: pass

def run_rsa_sniper():
    print(f"Connecting to SEC...")
    
    # --- INTELLIGENT DOWNLOADING ---
    if FORCE_TEST_TICKER:
        print(f"--- MODE: SURGICAL STRIKE ({FORCE_TEST_TICKER}) ---")
        try:
            company = Company(FORCE_TEST_TICKER)
            filings = company.get_filings(form="8-K").latest(10)
            print(f"SUCCESS: Downloaded {len(filings)} filings.")
        except Exception as e:
            print(f"Error finding ticker {FORCE_TEST_TICKER}: {e}")
            return
    else:
        # LIVE MODE - Fast Scan
        try:
            filings = get_filings(form=["8-K", "6-K"]).latest(50)
            print(f"SUCCESS: Downloaded {len(filings)} filings.")
        except Exception as e:
            print(f"SEC Error: {e}")
            return

    count_checked = 0

    for filing in filings:
        ticker = "UNKNOWN"
        
        # 1. Ticker Resolution
        if FORCE_TEST_TICKER:
            ticker = FORCE_TEST_TICKER
        else:
            try:
                if filing.ticker: ticker = filing.ticker
                else: ticker = str(filing.company).upper()[:15] # Use Name if Ticker missing
            except: pass

        count_checked += 1
        print(f"Scanning {ticker}...")

        try:
            main_text = filing.text()
            if not main_text: continue
            
            status = check_gold_status(main_text)
            
            if status == "NONE":
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        if check_gold_status(att_text) == "GUARANTEED": 
                            status = "GUARANTEED"
                            main_text = att_text
                            break
                    except: continue
            
            if status == "GUARANTEED":
                price = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                
                # --- THE "PENNY STOCK" GUARD ---
                # If price is > $1.00, it is likely POST-SPLIT (Expired).
                # We mark it expired to verify the logic, but kill the profit math.
                if price > 1.00:
                    is_expired = True
                    price_note = f"${price:.2f} (Suspiciously High - Likely Post-Split)"
                else:
                    price_note = f"${price:.2f}"

                # DECISION TO ALERT
                show_alert = False
                if FORCE_TEST_TICKER: show_alert = True
                elif not is_expired and price > 0 and ratio > 0: show_alert = True

                if show_alert:
                    if is_expired:
                         header = "⛔ EXPIRED / DONE"
                         calc = "Status: Split likely complete."
                    else:
                         header = "🚨 LIVE RSA FOUND"
                         est_value = price * ratio
                         profit = est_value - price
                         calc = f"PROFIT: ${profit:.2f} per share"

                    msg = (
                        f"{header}: {ticker}\n"
                        f"-------------------------\n"
                        f"{calc}\n"
                        f"Price: {price_note}\n"
                        f"Split: 1-for-{ratio}\n"
                        f"Effective: {eff_date}\n"
                        f"Link: {filing.url}"
                    )
                    print(f">>> HIT: {ticker} <<<")
                    send_telegram_msg(msg)
                    
                    if FORCE_TEST_TICKER: return # Stop after 1 hit in test mode

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} files.")

if __name__ == "__main__":
    run_rsa_sniper()
