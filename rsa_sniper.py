import os
import requests
import re
import yfinance as yf
from datetime import datetime
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

def get_stock_data(ticker):
    """
    Pulls live data from Yahoo Finance.
    Returns: Price, Float, Market Cap
    """
    if ticker == "UNKNOWN":
        return "N/A", "N/A", "N/A"
    
    try:
        stock = yf.Ticker(ticker)
        # Fast info fetch
        info = stock.fast_info
        
        # Get Price
        price = info.last_price
        if not price: price = 0.0
        
        # Get Shares/Market Cap (using standard info if fast_info fails)
        try:
            full_info = stock.info
            shares = full_info.get('sharesOutstanding', 0)
            mcap = full_info.get('marketCap', 0)
        except:
            shares = 0
            mcap = 0
        
        # Format Market Cap to Millions (e.g., 5.4M)
        if mcap > 1000000:
            mcap_str = f"${mcap/1000000:.2f}M"
        else:
            mcap_str = f"${mcap}"
            
        # Format Float/Shares to Millions
        if shares > 1000000:
            shares_str = f"{shares/1000000:.2f}M"
        else:
            shares_str = str(shares)

        return f"{price:.2f}", shares_str, mcap_str
    except:
        return "Error", "Error", "Error"

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # sending plain text so links don't break
    params = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_text_for_gold(text):
    if not text: return False, False
    clean_text = re.sub(r'\s+', ' ', text).lower()

    # Positive Rounding Logic
    pos_patterns = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)

    # Negative Cash Logic
    neg_patterns = [r"cash in lieu", r"cash payment", r"rounded down"]
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    return has_pos, has_neg

def run_rsa_sniper():
    print("Connecting to SEC...")
    seen_filings = load_seen_filings()
    
    try:
        # Looking at latest 2000 to be safe
        filings = get_filings().latest(2000)
    except Exception as e:
        print(f"SEC Connection Error: {e}")
        return

    target_forms = ["8-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    
    count_checked = 0
    
    # Get current time for "Popped At"
    # We adjust to ET roughly by adding hours if needed, but server time is usually UTC
    found_at = datetime.now().strftime("%I:%M %p")

    for filing in filings:
        if filing.form not in target_forms:
            continue
            
        # Check Memory (So we don't spam you with old news)
        if filing.accession_number in seen_filings:
            continue
        
        count_checked += 1
        
        try:
            ticker = filing.ticker if filing.ticker else "UNKNOWN"
            
            # PHASE 1: Main Text Scan
            main_text = filing.text()
            if not main_text: continue
            
            clean_main = re.sub(r'\s+', ' ', main_text).lower()
            if "reverse" not in clean_main and "split" not in clean_main:
                continue

            has_pos, has_neg = check_text_for_gold(main_text)
            
            # PHASE 2: Attachment Scan
            if not has_pos and not has_neg:
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        p, n = check_text_for_gold(att_text)
                        if p: has_pos = True
                        if n: has_neg = True
                        if has_pos or has_neg: break 
                    except:
                        continue

            if has_pos and not has_neg:
                # 2. MATCH FOUND! Get Stock Data
                price, shares, mcap = get_stock_data(ticker)
                
                msg = (
                    f"RSA GOLD DETECTED\n"
                    f"------------------\n"
                    f"Ticker: {ticker}\n"
                    f"Price: ${price}\n"
                    f"Float/OS: {shares}\n"
                    f"Market Cap: {mcap}\n"
                    f"------------------\n"
                    f"Filing Date: {filing.filing_date}\n"
                    f"Popped At: {found_at}\n"
                    f"Link: {filing.url}"
                )
                
                print(f">>> SENDING ALARM for {ticker} <<<")
                send_telegram_msg(msg)
                save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} relevant documents.")

if __name__ == "__main__":
    run_rsa_sniper()
