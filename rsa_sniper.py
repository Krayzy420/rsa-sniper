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

def verify_roundup(text, company_name):
    if not text: return False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # TRAP: If name contains "Noodles", print the text to prove we see it
    if "noodles" in company_name.lower():
        print(f"\n--- [NDLS TRAP TRIGGERED] ---")
        print(f"Company: {company_name}")
        # Print a snippet of the text to confirm we are reading it
        print(f"Text Snippet: {clean_text[:200]}...")
        
        # Check logic explicitly for debug
        pos_check = any(re.search(p, clean_text) for p in [r"round(ed|ing)? up", r"next whole share"])
        neg_check = any(re.search(p, clean_text) for p in [r"cash in lieu"])
        print(f"DEBUG: Found Positive? {pos_check} | Found Negative? {neg_check}")
        print("-----------------------------\n")

    # Standard RSA Logic
    if "reverse" not in clean_text and "split" not in clean_text:
        return False

    pos = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    neg = [r"cash in lieu", r"cash payment", r"rounded down"]
    
    has_pos = any(re.search(p, clean_text) for p in pos)
    has_neg = any(re.search(p, clean_text) for p in neg)
    
    return has_pos and not has_neg

def run_rsa_sniper():
    seen_filings = load_seen_filings()
    
    print("Connecting to SEC to pull latest 2,000 filings...")
    try:
        filings = get_filings().latest(2000)
        print(f"SUCCESS: Downloaded list of {len(filings)} filings.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return

    target_forms = ["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    
    count_checked = 0
    for filing in filings:
        if filing.form not in target_forms:
            continue
            
        count_checked += 1
        company = filing.company # Get the Name, not the Ticker
        
        # Progress marker (Show Name instead of UNKNOWN)
        if count_checked % 50 == 0:
            print(f"Scanning... (At: {company})")

        try:
            full_text = filing.text()
            
            # Use Company Name for identification
            if verify_roundup(full_text, company):
                # Try to get ticker, default to "UNKNOWN" if missing
                ticker = filing.ticker if filing.ticker else "UNKNOWN"
                
                msg = (
                    f"🎯 *RSA GOLD DETECTED*\n"
                    f"Company: {company}\n"
                    f"Ticker: {ticker}\n"
                    f"Date: {filing.filing_date}\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)
                print(f">>> ALARM SENT for {company} <<<")
                
        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} relevant documents.")

if __name__ == "__main__":
    run_rsa_sniper()
