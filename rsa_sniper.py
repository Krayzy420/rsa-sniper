import os
import requests
import re
from edgar import *

# SEC Identity
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
    """
    Secondary Validation: Returns True only if 'Round Up' logic 
    exists without 'Cash' logic in the same vicinity.
    """
    # 1. Clean the text for easier reading
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # 2. Find the 'Fractional' or 'Round' section (the next 500 characters)
    split_match = re.search(r"reverse (stock )?split", clean_text)
    if not split_match:
        return False
        
    context = clean_text[split_match.start():split_match.start() + 1000]
    
    # 3. Search for 'Guaranteed' phrases
    positive_patterns = [
        r"rounded up to the (nearest|next) whole share",
        r"rounding up",
        r"rounded up to the next higher",
        r"upwardly adjusted",
        r"elevated to the next",
        r"round lot"
    ]
    
    negative_patterns = [
        r"cash in lieu",
        r"cash payment",
        r"no fractional shares will be issued", # Can be positive or negative; context matters
        r"fractional shares will be canceled"
    ]
    
    # Logic: Must have a positive pattern AND not have a negative pattern in the context
    has_positive = any(re.search(p, context) for p in positive_patterns)
    has_negative = any(re.search(p, context) for p in negative_patterns)
    
    # If it has a positive term and NO cash terms, it's a high-probability RSA
    return has_positive and not has_negative

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    # Pulling 1000 filings for a complete daily safety net
    filings = get_filings(form=["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]).latest(1000)
    
    print(f"Deep scanning 1000 filings...")

    for filing in filings:
        if filing.accession_number in seen_filings:
            continue
            
        full_text = filing.text()
        
        # Double-check the wording
        if verify_roundup(full_text):
            msg = (
                f"🎯 *RSA GOLD DETECTED*\n"
                f"Ticker: {filing.ticker}\n"
                f"Company: {filing.company}\n"
                f"Confidence: High (Verified Rounding)\n"
                f"Link: {filing.url}"
            )
            send_telegram_msg(msg)
            save_seen_filing(filing.accession_number)

if __name__ == "__main__":
    run_rsa_sniper()
