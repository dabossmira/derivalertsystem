from flask import Flask, render_template, request, redirect, url_for
import websocket
import json
import threading

app = Flask(__name__)

# Global variable to store alerts
alert_prices = {}

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
                print(f"ALERT: {symbol} has reached the desired price of {target_price}! Current price: {price}. Message: {custom_message}")
                del alert_prices[symbol]  # Remove the alert after triggering

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
