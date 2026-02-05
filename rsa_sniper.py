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
    if not text:
        return False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    split_match = re.search(r"reverse (stock )?split", clean_text)
    if not split_match:
        return False
    context = clean_text[split_match.start():split_match.start() + 1200]
    
    positive_patterns = [
        r"rounded up to the (nearest|next) whole share",
        r"rounding up",
        r"rounded up to the next higher",
        r"upwardly adjusted",
        r"elevated to the next",
        r"round lot"
    ]
    negative_patterns = [r"cash in lieu", r"cash payment", r"fractional shares will be canceled"]
    
    has_positive = any(re.search(p, context) for p in positive_patterns)
    has_negative = any(re.search(p, context) for p in negative_patterns)
    return has_positive and not has_negative

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    print(f"Deep scanning 1000 filings...")
    
    try:
        filings = get_filings(form=["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]).latest(1000)
    except Exception as e:
        print(f"Error fetching filings: {e}")
        return

    for filing in filings:
        if filing.accession_number in seen_filings:
            continue
            
        try:
            # SAFETY GATE: Check if text exists before processing
            full_text = filing.text()
            if full_text and verify_roundup(full_text):
                msg = (
                    f"🎯 *RSA GOLD DETECTED*\n"
                    f"Ticker: {filing.ticker}\n"
                    f"Company: {filing.company}\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)
        except Exception as e:
            # If one filing is broken, just skip it and move to the next
            print(f"Skipping filing {filing.accession_number} due to error: {e}")
            continue

if __name__ == "__main__":
    run_rsa_sniper()
