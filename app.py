from flask import Flask, render_template, request, redirect, url_for
import websocket
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get secrets from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TO_EMAIL = os.getenv('TO_EMAIL')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Define WebSocket URL for Deriv API
DERIV_API_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"  # Replace 1089 with your app_id

# Initialize Flask app
app = Flask(__name__)

alert_prices = {}

def send_email(subject, message):
    """Function to send email using SSL."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))
    try:
        # Connect to the SMTP server using SSL
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

# Flask route for the homepage
@app.route('/')
def index():
    return render_template('index.html')

# Flask route to handle form submission
@app.route('/set_alert', methods=['POST'])
def set_alert():
    global alert_prices
    instrument = request.form['instrument']
    target_price = float(request.form['target_price'])
    custom_message = request.form['custom_message']

    alert_prices[instrument] = {
        'target_price': target_price,
        'custom_message': custom_message
    }

    return redirect(url_for('index'))

# Function to handle incoming WebSocket messages
def on_message(ws, message):
    data = json.loads(message)
    if 'tick' in data:
        symbol = data['tick']['symbol']
        price = data['tick']['quote']
        timestamp = data['tick']['epoch']
        print(f"Instrument: {symbol}, Price: {price}, Timestamp: {timestamp}")

        tolerance = 0.1  # Small tolerance for price comparison

        if symbol in alert_prices:
            target_price = alert_prices[symbol]['target_price']
            custom_message = alert_prices[symbol]['custom_message']
            if abs(price - target_price) <= tolerance:
                alert_message = f"ALERT: {symbol} has reached the desired price of {target_price}! Current price: {price}\n{custom_message}"
                print(f"*** {alert_message} ***")

                # Send an email alert
                send_email(subject=f"Price Alert for {symbol}", message=alert_message)

                # Send a Telegram alert
                send_telegram_message(alert_message)

                del alert_prices[symbol]

                if not alert_prices:
                    print("All price alerts triggered. Closing WebSocket connection.")
                    ws.close()

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket connection closed")

def on_open(ws):
    print("WebSocket connection opened")
    for instrument in alert_prices.keys():
        subscribe_message = json.dumps({"ticks": instrument})
        ws.send(subscribe_message)

@app.route('/start_ws')
def start_ws():
    # Create WebSocket App instance and run the WebSocket connection
    ws = websocket.WebSocketApp(DERIV_API_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()
    return "WebSocket started"

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
