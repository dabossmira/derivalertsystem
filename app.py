from flask import Flask, render_template, request, jsonify
import os
import json
import websocket
import threading
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Get the environment variables
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Global variables to store alert details and logs
alert_prices = {}
logs = []

# Email function
def send_email(subject, message, recipient_email):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")

# Telegram notification function
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Message sent to Telegram.")
        else:
            print(f"Failed to send message to Telegram. Response: {response.text}")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# WebSocket message handling
def on_message(ws, message):
    global logs
    data = json.loads(message)
    
    if 'tick' in data:
        symbol = data['tick']['symbol']
        price = data['tick']['quote']
        log_message = f"{symbol} price: {price}"
        
        # Keep only the 3 most recent logs
        if len(logs) >= 3:
            logs.pop(0)
        logs.append(log_message)

        if symbol in alert_prices:
            target_price = alert_prices[symbol]['target_price']
            custom_message = alert_prices[symbol]['custom_message']
            email = alert_prices[symbol]['email']
            if price >= target_price:
                alert_message = f"ALERT: {symbol} reached target price of {target_price}. Current price: {price}. Message: {custom_message}"
                send_email(subject=f"Price Alert for {symbol}", message=alert_message, recipient_email=email)
                send_telegram_message(alert_message)
                del alert_prices[symbol]  # Remove the triggered alert

# WebSocket functions
def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws):
    print("WebSocket connection closed")

def on_open(ws):
    for instrument in alert_prices.keys():
        ws.send(json.dumps({"ticks": instrument}))

def run_websocket():
    ws = websocket.WebSocketApp("wss://ws.binaryws.com/websockets/v3?app_id=1089",
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_alert', methods=['POST'])
def set_alert():
    instrument = request.form['instrument']
    target_price = float(request.form['target_price'])
    custom_message = request.form['custom_message']
    email = request.form['email']
    
    # Store the alert information
    alert_prices[instrument] = {
        'target_price': target_price,
        'custom_message': custom_message,
        'email': email
    }
    
    # Start WebSocket in a separate thread
    threading.Thread(target=run_websocket).start()

    return jsonify({"status": "WebSocket started", "logs": logs})

@app.route('/logs', methods=['GET'])
def get_logs():
    return jsonify(logs[-3:])  # Return only the 3 most recent logs

if __name__ == '__main__':
    app.run(debug=True)
