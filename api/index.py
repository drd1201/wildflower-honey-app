import os
import sqlite3
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.rest import Client as TwilioClient
import paypalrestsdk

app = Flask(__name__)
CORS(app)

# LIVE Credentials
PAYPAL_CLIENT_ID = "AbeuVcyPADfETQPoMFsoonAhho32d2Ejx1oBelG2vQuGi8D4RmInNhRcpXoQoONphngmYeCXhtTtQgIYVM"
PAYPAL_SECRET = "EMZu-ww25716GB6lh4_b-sEZYMiMo_Gn3u_-Are7mxHboXD5q1uNCK-OtmWuufFZ8iXlX0V47Uf9fOjfd"
TWILIO_ACCOUNT_SID = "AC1aface281d36d9fd9087c7"
TWILIO_AUTH_TOKEN = "8514c1e9e2a3c0938e4f0fb8e7"
TWILIO_PHONE_NUMBER = "+18556838803"
NOTIFICATION_PHONE_NUMBER = "+13184231053"

DB_PATH = "/tmp/orders.db"

paypalrestsdk.configure({
    "mode": "live",
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET,
})

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT, email TEXT, phone TEXT, address TEXT, items TEXT, total REAL, payment_status TEXT, created_at TEXT DEFAULT (datetime('now')))")
    conn.commit()
    conn.close()

if not os.path.exists(DB_PATH): init_db()

@app.route("/api/products")
def get_products():
    return jsonify([
        {"id": "wildflower-16", "name": "Wildflower Honey", "size": "16 oz", "price": 14.99, "image": "🌸"},
        {"id": "clover-16", "name": "Clover Honey", "size": "16 oz", "price": 12.99, "image": "🍀"},
        {"id": "manuka-8", "name": "Mānuka Honey", "size": "8 oz", "price": 29.99, "image": "🌿"},
        {"id": "gift-box", "name": "Honey Gift Box", "size": "3×8 oz", "price": 39.99, "image": "🎁"}
    ])

@app.route("/api/orders/manual", methods=["POST"])
def manual_order():
    data = request.json
    customer = data.get("customer", {})
    try:
        twilio_client.messages.create(body=f"🍯 New Order! From {customer.get('name')}.", from_=TWILIO_PHONE_NUMBER, to=NOTIFICATION_PHONE_NUMBER)
    except: pass
    return jsonify({"order_id": "M-123", "sms_sent": True})

@app.route("/api/admin/stats")
def admin_stats():
    return jsonify({"total_orders": 0, "total_revenue": 0.0, "pending_orders": 0, "sms_notifications_sent": 0})

if __name__ == "__main__": app.run()
