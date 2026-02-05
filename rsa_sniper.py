import os
import requests

def send_test():
    # This pulls the 'Secrets' you saved in GitHub Settings
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    message = "ALARM TEST: Kevin, if you see this, your Telegram connection is PERFECT."
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
    
    print("Sending test message...")
    response = requests.get(url)
    print(f"Response from Telegram: {response.text}")

if __name__ == "__main__":
    send_test()
