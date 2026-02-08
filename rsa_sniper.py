import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- MANUAL TARGET LIST ---
# WE ARE HARD-CODING THESE SO YOU DON'T HAVE TO TYPE THEM.
# The bot will force a deep scan on THESE specific stocks.
MANHUNT_TARGETS = ["HERZ", "HTZ", "EDBL"] 

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
    
    # Check 1-for-X
    match = re.search(r'1-for-([0-9]+)', clean_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
    
    # Check X-for-1
    if ratio == 0:
        match = re.search(r'([0-9]+)-for-1 (share )?consolidation', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    # Date Check
    date_str = "Unknown"
    is_expired = False
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

    # KILLER PHRASES (Trash)
    bad_patterns = [r"cash (payment )?in lieu", r"paid in cash", r"rounded down"]
    if any(re.search(p, clean_text) for p in bad_patterns):
        return "BAD"

    # GOLD PHRASES (Good)
    good_patterns = [r"round(ed|ing)? up", r"whole share", r"upward adjustment", 
                     r"nearest whole number", r"no fractional shares.*issued"]
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
    print(f"--- MODE: MANHUNT (Targets: {MANHUNT_TARGETS}) ---")
    print(f"Connecting to SEC...")
    
    for ticker in MANHUNT_TARGETS:
        print(f"🔎 HUNTING TARGET: {ticker}...")
        try:
            # FORCE DOWNLOAD FOR THIS TICKER
            try:
                company = Company(ticker)
                filings = company.get_filings(form="8-K").latest(20)
            except:
                print(f"   ❌ Could not find filings for {ticker} (May be invalid symbol)")
                continue

            if not filings:
                print(f"   ⚠️ No 8-K filings found for {ticker}")
                continue

            print(f"   ✅ Found {len(filings)} filings. Scanning...")

            for filing in filings:
                try:
                    main_text = filing.text()
                    if not main_text: continue
                    
                    status = check_gold_status(main_text)
                    
                    # If not in main text, check attachments
                    if status == "NONE":
                        for attachment in filing.attachments:
                            try:
                                if check_gold_status(attachment.text()) == "GUARANTEED": 
                                    status = "GUARANTEED"
                                    main_text = attachment.text()
                                    break
                            except: continue
                    
                    if status == "GUARANTEED":
                        price = get_stock_data(ticker)
                        ratio, eff_date, is_expired = analyze_split_data(main_text)
                        
                        if ratio == 0: continue

                        # --- ALERT GENERATION ---
                        if is_expired:
                            header = f"⛔ {ticker}: EXPIRED (History)"
                            calc = "Split Completed"
                        else:
                            header = f"🚨 {ticker}: LIVE RSA"
                            calc = f"PROFIT: ${(price*ratio)-price:.2f}"

                        price_str = f"Price: ${price:.2f}" if price > 0 else "Price: UNKNOWN"

                        msg = (
                            f"{header}\n"
                            f"-------------------------\n"
                            f"{calc}\n"
                            f"{price_str}\n"
                            f"Split: 1-for-{ratio}\n"
                            f"Effective: {eff_date}\n"
                            f"Link: {filing.url}"
                        )
                        print(f">>> HIT FOUND: {ticker} <<<")
                        send_telegram_msg(msg)
                        
                        # Stop after finding the most recent one for this ticker
                        break 

                except Exception as e:
                    pass

        except Exception as e:
            print(f"System Error on {ticker}: {e}")

    print("Manhunt Complete.")

if __name__ == "__main__":
    run_rsa_sniper()
