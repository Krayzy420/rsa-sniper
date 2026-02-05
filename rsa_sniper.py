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

def verify_roundup(text):
    if not text: return False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    split_match = re.search(r"reverse (stock )?split", clean_text)
    if not split_match: return False
    
    context = clean_text[max(0, split_match.start()-500):split_match.start() + 1500]
    
    # FIXED: Added "round up" (present tense) to catch NDLS
    pos = [
        r"round(ed|ing)? up",       # Catches: round up, rounded up, rounding up
        r"next whole share",        # Catches: "to the next whole share" (NDLS phrasing)
        r"next higher whole", 
        r"nearest whole share",
        r"round lot",
        r"upwardly adjusted"
    ]
    
    # Negative checks (Cash in Lieu)
    neg = [r"cash in lieu", r"cash payment", r"rounded down"]
    
    has_pos = any(re.search(p, context) for p in pos)
    has_neg = any(re.search(p, context) for p in neg)
    
    return has_pos and not has_neg

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    
    # TRIPLE CHECK: Today + Yesterday
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    dates_to_check = [today.strftime('%Y-%m-%d'), yesterday.strftime('%Y-%m-%d')]
    target_forms = ["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    
    for date_str in dates_to_check:
        print(f"--- TRIPLE CHECK: Scanning ALL filings for {date_str} ---")
        filings = get_filings(form=target_forms, filing_date=date_str)
        
        if filings is None: continue

        for filing in filings:
            if filing.accession_number in seen_filings:
                continue
            
            try:
                full_text = filing.text()
                if verify_roundup(full_text):
                    msg = (
                        f"🎯 *RSA GOLD DETECTED*\n"
                        f"Ticker: {filing.ticker}\n"
                        f"Date: {filing.filing_date}\n"
                        f"Link: {filing.url}"
                    )
                    send_telegram_msg(msg)
                    save_seen_filing(filing.accession_number)
            except Exception as e:
                pass 

if __name__ == "__main__":
    run_rsa_sniper()
