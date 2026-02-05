import os
import requests
import re
from edgar import *

# Identify to SEC
set_identity("Kevin Anderson kevinand83@gmail.com")

DB_FILE = "seen_filings.txt"

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown"
    requests.get(url)

def verify_roundup(text, ticker):
    if not text: return False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # 1. Broad Split Check
    if "reverse" not in clean_text or "split" not in clean_text:
        return False

    print(f"[{ticker}] MATCH: Found 'Reverse Split' in text. Analyzing...")

    # 2. Precise Rounding Check
    pos = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted", r"no fractional shares"]
    neg = [r"cash in lieu", r"cash payment", r"rounded down"]
    
    has_pos = any(re.search(p, clean_text) for p in pos)
    has_neg = any(re.search(p, clean_text) for p in neg)
    
    if has_neg:
        print(f"  X [{ticker}] REJECTED: Found 'Cash in Lieu' logic.")
        return False
        
    if has_pos:
        print(f"  >>> [{ticker}] SUCCESS: Found Rounding Logic! <<<")
        return True
    
    print(f"  X [{ticker}] REJECTED: No specific rounding/cash instructions found.")
    return False

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    
    print("Connecting to SEC to pull latest 2,000 filings...")
    try:
        filings = get_filings().latest(2000)
        print(f"SUCCESS: Downloaded list of {len(filings)} filings.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not download filings. {e}")
        return

    target_forms = ["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    
    count_checked = 0
    for filing in filings:
        if filing.form not in target_forms:
            continue
            
        # We temporarily REMOVED the "seen_filings" check so it re-scans NDLS every time for testing
        # if filing.accession_number in seen_filings: continue
            
        count_checked += 1
        
        try:
            full_text = filing.text()
            if verify_roundup(full_text, filing.ticker):
                msg = (
                    f"🎯 *RSA GOLD DETECTED*\n"
                    f"Ticker: {filing.ticker}\n"
                    f"Form: {filing.form}\n"
                    f"Date: {filing.filing_date}\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)
                print(f"ALARM SENT for {filing.ticker}")
        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} relevant documents.")

if __name__ == "__main__":
    run_rsa_sniper()
