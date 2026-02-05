import os
import requests
import re
from datetime import datetime, timedelta
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
    
    # 1. Check for Split Mention
    if "reverse" not in clean_text or "split" not in clean_text:
        return False

    print(f"  -> Found 'Reverse Split' in {ticker}. Checking for Rounding...")

    # 2. Check for Rounding Logic (ANYWHERE in the text)
    # Added "round up" (present tense) specifically for NDLS
    pos_patterns = [
        r"round(ed|ing)? up", 
        r"to the next whole", 
        r"nearest whole share",
        r"upwardly adjusted",
        r"no fractional shares(.*?)issued" # Often implies rounding if cash isn't mentioned
    ]
    
    # 3. Check for Cash Logic (The "Killer")
    neg_patterns = [
        r"cash in lieu", 
        r"cash payment", 
        r"otherwise be entitled to receive a fractional share(.*?)cash",
        r"rounded down"
    ]
    
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    if has_pos:
        print(f"  -> Found ROUNDING logic in {ticker}!")
    if has_neg:
        print(f"  -> Found CASH logic in {ticker} (Trade Killed).")

    # ONLY return true if we have Positive and NO Negative
    return has_pos and not has_neg

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # Checking Today and Yesterday
    dates_to_check = [today.strftime('%Y-%m-%d'), yesterday.strftime('%Y-%m-%d')]
    target_forms = ["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    
    for date_str in dates_to_check:
        print(f"--- TRIPLE CHECK: Scanning ALL filings for {date_str} ---")
        try:
            filings = get_filings(form=target_forms, filing_date=date_str)
        except Exception as e:
            print(f"Error connecting to SEC: {e}")
            continue
        
        if not filings: continue

        for filing in filings:
            if filing.accession_number in seen_filings:
                continue
            
            try:
                # Basic filter to save time: skip if "split" isn't in the description
                # But read text just to be safe if it's an 8-K
                full_text = filing.text()
                
                if verify_roundup(full_text, filing.ticker):
                    msg = (
                        f"🎯 *RSA GOLD DETECTED*\n"
                        f"Ticker: {filing.ticker}\n"
                        f"Date: {filing.filing_date}\n"
                        f"Link: {filing.url}"
                    )
                    send_telegram_msg(msg)
                    save_seen_filing(filing.accession_number)
                    print(f"SUCCESS: Alert sent for {filing.ticker}")
            except Exception as e:
                # Ignore random read errors
                pass

if __name__ == "__main__":
    run_rsa_sniper()
