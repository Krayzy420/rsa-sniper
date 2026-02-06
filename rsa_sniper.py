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

# FIXED: Now handles symbols like '&' correctly
def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Sending data as 'params' automatically handles special characters
    params = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_text_for_gold(text):
    if not text: return False, False
    clean_text = re.sub(r'\s+', ' ', text).lower()

    # 1. Check for Rounding (Positive)
    pos_patterns = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)

    # 2. Check for Cash (Negative)
    neg_patterns = [r"cash in lieu", r"cash payment", r"rounded down"]
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    return has_pos, has_neg

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
        company = filing.company
        
        try:
            ticker = filing.ticker if filing.ticker else "UNKNOWN"
        except:
            ticker = "UNKNOWN"

        if count_checked % 50 == 0:
            print(f"Scanning... (At: {company})")

        try:
            # Check the Memory File FIRST to prevent re-alerting on old stuff
            # (Remove this 'if' statement only if you want to test NDLS again)
            if filing.accession_number in seen_filings and ticker != "NDLS":
                continue

            # PHASE 1: Check Main Document
            main_text = filing.text()
            if not main_text: continue
            
            clean_main = re.sub(r'\s+', ' ', main_text).lower()
            if "reverse" not in clean_main and "split" not in clean_main:
                continue

            has_pos, has_neg = check_text_for_gold(main_text)
            
            # PHASE 2: Drill Down into Attachments
            if not has_pos and not has_neg:
                print(f"  -> Found Split in {company}, drilling into attachments...")
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        p, n = check_text_for_gold(att_text)
                        if p: has_pos = True
                        if n: has_neg = True
                        if has_pos or has_neg: break 
                    except:
                        continue

            # FINAL VERDICT
            if has_pos and not has_neg:
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
