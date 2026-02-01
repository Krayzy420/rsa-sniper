import os
import requests
from edgar import *

# Tell the SEC who is looking at the data
set_identity("Kevin Anderson krayzyllc@gmail.com")

def send_telegram_msg(message):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown"
    requests.get(url)

def run_rsa_sniper():
    # Scanning the 20 most recent filings
    filings = get_filings(form=["8-K", "DEF 14A", "PRE 14A"]).latest(20)
    
    # The wording you need for the "Round Up" trade to work
    target_logic = ["rounded up to the nearest whole share", "rounded up to the next whole share", "rounding up"]

    for filing in filings:
        text = filing.text().lower()
        if "reverse" in text and "split" in text:
            if any(phrase in text for phrase in target_logic):
                msg = f"🎯 *RSA TRADE ALERT*\nTicker: {filing.ticker}\nCompany: {filing.company}\nProvision: Rounding Up Found\nLink: {filing.url}"
                send_telegram_msg(msg)

if __name__ == "__main__":
    run_rsa_sniper()
