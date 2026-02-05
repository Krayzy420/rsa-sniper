import os
import requests

def manual_test():
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    # This will print in the GitHub log so we can see what's happening
    print(f"DEBUG: Using Chat ID starting with: {str(chat_id)[:4]}...")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": "BOT TEST: If you see this, the wiring is fixed."}
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        print("SUCCESS: Telegram says the message was delivered!")
    else:
        print(f"FAILED: Error {response.status_code}")
        print(f"Response from Telegram: {response.text}")

if __name__ == "__main__":
    manual_test()
