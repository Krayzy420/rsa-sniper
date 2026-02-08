import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- THE VERIFIED TARGET LIST ---
VERIFIED_DATA = {
    "WTO": {"ratio": 5, "effective": "2026-02-17", "cutoff": "2026-02-13"}, 
    "ANY": {"ratio": 10, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "ATPC": {"ratio": 50, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "HERZ": {"ratio": 10, "effective": "2026-02-09", "cutoff": "2026-02-06"}
}

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def run_rsa_sniper():
    now = datetime.now()
    seen_filings = load_seen_filings()
    
    for ticker, info in VERIFIED_DATA.items():
        # (Standard price/date logic...)
        
        # --- PREVENT DUPLICATES ---
        # Generate a unique key for this alert (Ticker + Status)
        alert_id = f"{ticker}_{now.strftime('%Y-%m-%d')}"
        if alert_id in seen_filings:
            continue # Already sent today, skip it

        # --- ALARM & STATUS LOGIC ---
        # (Logic to send the alert...)

        # Record that we sent this so we don't spam
        save_seen_filing(alert_id)

if __name__ == "__main__":
    run_rsa_sniper()
