import os
import requests
import yfinance as yf
from datetime import datetime

# --- CONFIGURATION ---
# We are FORCING this to "NDLS" so you see a result immediately.
# After you get the text, change this to: TEST_TICKER = None
TEST_TICKER = "NDLS"
# ---------------------

def get_stock_data(ticker):
    print(f"Fetching data for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        
        # Try Fast Info (Real-time)
        try:
            price = stock.fast_info.last_price
        except:
            price = stock.info.get('currentPrice')
            
        # Try Share Data
        try:
            shares = stock.info.get('sharesOutstanding', 0)
            mcap = stock.info.get('marketCap', 0)
        except:
            shares = 0
            mcap = 0
            
        # Formatting
        if price:
            price_str = f"${price:.2f}"
        else:
            price_str = "N/A"
            
        if mcap and mcap > 1000000:
            mcap_str = f"${mcap/1000000:.2f}M"
        else:
            mcap_str = f"${mcap}"
            
        if shares and shares > 1000000:
            shares_str = f"{shares/1000000:.2f}M"
        else:
            shares_str = str(shares)
            
        return price_str, shares_str, mcap_str
        
    except Exception as e:
        print(f"Finance Error: {e}")
        return "Error", "Error", "Error"

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    try:
        print(f"Sending Message to Telegram...")
        requests.get(url, params=params)
        print("Message SENT.")
    except Exception as e:
        print(f"Telegram Failed: {e}")

def run_test():
    print(f"--- RUNNING DIRECT TEST ON {TEST_TICKER} ---")
    
    # 1. Get Data
    price, shares, mcap = get_stock_data(TEST_TICKER)
    print(f"Data Found: Price={price}, Float={shares}, Cap={mcap}")
    
    # 2. Build Message
    found_at = datetime.now().strftime("%I:%M %p")
    msg = (
        f"⚠️ SYSTEM TEST ⚠️\n"
        f"------------------\n"
        f"Ticker: {TEST_TICKER}\n"
        f"Price: {price}\n"
        f"Float: {shares}\n"
        f"Mkt Cap: {mcap}\n"
        f"------------------\n"
        f"Time: {found_at} ET\n"
        f"Status: FINANCE TOOL IS WORKING"
    )
    
    # 3. Send
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_test()
