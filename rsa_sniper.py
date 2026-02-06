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

# NEW FUNCTION: Safely get the ticker without crashing
def get_ticker_safe(filing):
    try:
        return filing.ticker
    except:
        return "UNKNOWN"

def verify_roundup(text, ticker):
    if not text: 
        return False
        
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # TRAP: If it's NDLS, print the first 500 characters so we can see what the bot sees
    if ticker == "NDLS":
        print(f"\n--- [NDLS TRAP TRIGGERED] ---")
        print(f"Snippet: {clean_text[:500]}...")
        print("-----------------------------\n")

    if "reverse" not in clean_text and "split" not in clean_text:
        return False

    # Rounding Check
    pos = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    neg = [r"cash in lieu", r"cash payment", r"rounded down"]
    
    has_pos = any(re.search(p, clean_text) for p in pos)
    has_neg = any(re.search(p, clean_text) for p in neg)
    
    if ticker == "NDLS":
        print(f"NDLS DEBUG -> Has Positive: {has_pos} | Has Negative: {has_neg}")

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
        
        # USE SAFETY SHIELD
        ticker = get_ticker_safe(filing)
        count_checked += 1
        
        # Progress marker
        if count_checked % 50 == 0:
            print(f"Scanning... (Currently at {ticker})")

        try:
            # Force check NDLS
            if ticker == "NDLS":
                print(f"!!! FOUND NDLS in the list ({filing.form}) !!!")
            
            if ticker == "UNKNOWN":
                continue

            full_text = filing.text()
            
            if verify_roundup(full_text, ticker):
                msg = (
                    f"🎯 *RSA GOLD DETECTED*\n"
                    f"Ticker: {ticker}\n"
                    f"Date: {filing.filing_date}\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)
                print(f">>> ALARM SENT for {ticker} <<<")
                
        except Exception as e:
            # If a single file fails, just print error and keep moving
            # print(f"Skipping bad file: {e}")
            pass

    print(f"Run Complete. Scanned {count_checked} relevant documents.")

if __name__ == "__main__":
    run_rsa_sniper()
