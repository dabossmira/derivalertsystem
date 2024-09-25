from flask import Flask, render_template, request, redirect, url_for
import websocket
import json
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Global variable to store alerts
alert_prices = {}

# Email Configuration
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')  # Your email address from .env
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # Your email password or app password from .env
TO_EMAIL = os.getenv('TO_EMAIL')  # Recipient email address from .env

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Your Telegram bot token from .env
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Your Telegram chat ID from .env

def send_email(subject, message):
    """Function to send email using SSL."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {TO_EMAIL}")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")

def send_telegram_message(message):
    """Function to send a message to Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Message sent to Telegram.")
        else:
            print(f"Failed to send message to Telegram. Response: {response.text}")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_alert', methods=['POST'])
def set_alert():
    global alert_prices
    instrument = request.form['instrument']
    target_price = float(request.form['target_price'])
    custom_message = request.form['custom_message']

    # Add to alert prices
    alert_prices[instrument] = {
        'target_price': target_price,
        'custom_message': custom_message
    }
    
    print(f"Alert set for {instrument} at {target_price} with message: {custom_message}")
    return redirect(url_for('index'))

def on_message(ws, message):
    global alert_prices
    data = json.loads(message)
    
    if 'tick' in data:
        symbol = data['tick']['symbol']
        price = data['tick']['quote']
        print(f"Instrument: {symbol}, Price: {price}")

        # Check for alerts
        if symbol in alert_prices:
            target_price = alert_prices[symbol]['target_price']
            custom_message = alert_prices[symbol]['custom_message']
            if abs(price - target_price) <= 0.1:  # Using a tolerance of 0.1
                alert_message = (f"ALERT: {symbol} has reached the desired price of {target_price}! "
                                 f"Current price: {price}. Message: {custom_message}")
                print(alert_message)

                # Send alerts via email and Telegram
                send_email(subject=f"Price Alert for {symbol}", message=alert_message)
                send_telegram_message(alert_message)

                # Remove the alert after triggering
                del alert_prices[symbol]

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connection opened")
    # Subscribe to tick updates for each instrument
    for instrument in alert_prices.keys():
        subscribe_message = json.dumps({"ticks": instrument})
        ws.send(subscribe_message)

def start_ws():
    ws = websocket.WebSocketApp("wss://ws.binaryws.com/websockets/v3?app_id=1089",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

@app.route('/start_ws')
def start_ws_route():
    # Start WebSocket in a new thread to prevent blocking
    thread = threading.Thread(target=start_ws)
    thread.start()
    return "WebSocket started! Check console for updates."

if __name__ == "__main__":
    app.run(debug=True)