import os
import requests
from edgar import *

# 1. Identity set to your specific email to satisfy SEC requirements
set_identity("Kevin Anderson kevinand83@gmail.com")

def send_telegram_msg(message):
    # These look for the 'Keys' you saved in GitHub Settings
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("Error: Telegram secrets are missing in GitHub Settings.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown"
    requests.get(url)

def run_rsa_sniper():
    # 2. Scanning the 20 most recent filings for immediate trades
    filings = get_filings(form=["8-K", "DEF 14A", "PRE 14A"]).latest(20)
    
    # 3. The exact wording that triggers your 101-share strategy
    target_logic = [
        "rounded up to the nearest whole share", 
        "rounded up to the next whole share", 
        "rounding up",
        "round lot"
    ]

    print(f"Checking {len(filings)} filings for RSA wording...")

    for filing in filings:
        text = filing.text().lower()
        
        # We only care if it's a split AND has the rounding language
        if "reverse" in text and "split" in text:
            if any(phrase in text for phrase in target_logic):
                msg = (
                    f"🎯 *RSA TRADE DETECTED*\n"
                    f"Ticker: {filing.ticker}\n"
                    f"Company: {filing.company}\n"
                    f"Form: {filing.form}\n"
                    f"Action: Check for Rounding Up / Round Lot protection.\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                print(f"Match found for {filing.ticker}! Message sent.")

if __name__ == "__main__":
    run_rsa_sniper()
