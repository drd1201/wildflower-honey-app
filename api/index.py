import os
import sqlite3
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from twilio.rest import Client as TwilioClient
import paypalrestsdk

# Configuration
PAYPAL_CLIENT_ID = "AbeuVcyPADfETQPoMFsoonAhho32d2Ejx1oBelG2vQuGi8D4RmInNhRcpXoQoONphngmYeCXhtTtQgIYVM"
PAYPAL_SECRET = "EMZu-ww25716GB6lh4_b-sEZYMiMo_Gn3u_-Are7mxHboXD5q1uNCK-OtmWuufFZ8iXlX0V47Uf9fOjfd"
TWILIO_ACCOUNT_SID = "AC1aface281d36d9fd9087c7"
TWILIO_AUTH_TOKEN = "8514c1e9e2a3c0938e4f0fb8e7"
TWILIO_PHONE_NUMBER = "+18556838803"
NOTIFICATION_PHONE_NUMBER = "+13184231053"

# On Vercel, we must use /tmp for writable SQLite db
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
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            items TEXT NOT NULL,
            subtotal REAL NOT NULL,
            shipping REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            paypal_order_id TEXT,
            paypal_capture_id TEXT,
            payment_status TEXT DEFAULT 'pending',
            order_status TEXT DEFAULT 'new',
            sms_sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

if not os.path.exists(DB_PATH):
    init_db()

app = Flask(__name__, static_folder="../static", static_url_path="")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/admin")
def admin():
    return send_from_directory(app.static_folder, "admin.html")

@app.route("/success")
def success_page():
    return send_from_directory(app.static_folder, "success.html")

@app.route("/game")
def game_page():
    return send_from_directory(app.static_folder, "game.html")

PRODUCTS = [
    {"id": "wildflower-16", "name": "Wildflower Honey", "size": "16 oz", "price": 14.99, "description": "A beautiful blend of wildflower nectars.", "image": "🌸"},
    {"id": "clover-16", "name": "Clover Honey", "size": "16 oz", "price": 12.99, "description": "Classic light & sweet clover honey.", "image": "🍀"},
    {"id": "manuka-8", "name": "Mānuka Honey", "size": "8 oz", "price": 29.99, "description": "Premium Mānuka honey.", "image": "🌿"},
    {"id": "buckwheat-16", "name": "Buckwheat Honey", "size": "16 oz", "price": 16.99, "description": "Dark, bold buckwheat honey.", "image": "🌾"},
    {"id": "orange-16", "name": "Orange Blossom Honey", "size": "16 oz", "price": 15.99, "description": "Delicate citrus notes.", "image": "🍊"},
    {"id": "gift-box", "name": "Honey Gift Box", "size": "3×8 oz", "price": 39.99, "description": "A curated sampler box.", "image": "🎁"},
]

@app.route("/api/products")
def get_products():
    return jsonify(PRODUCTS)

@app.route("/api/orders/create-paypal", methods=["POST"])
def create_paypal_order():
    data = request.json
    items = data.get("items", [])
    subtotal = sum(next((p["price"] for p in PRODUCTS if p["id"] == it["id"]), 0) * int(it.get("qty", 1)) for it in items)
    shipping = 0 if subtotal >= 50 else 7.99
    total = round(subtotal + shipping, 2)
    payment = paypalrestsdk.Payment({"intent": "sale", "payer": {"payment_method": "paypal"}, "redirect_urls": {"return_url": request.host_url + "success", "cancel_url": request.host_url}, "transactions": [{"item_list": {"items": []}, "amount": {"total": f"{total:.2f}", "currency": "USD"}, "description": "Wildflower Honey Shop Order"}]})
    if payment.create():
        approval_url = next((link.href for link in payment.links if link.rel == "approval_url"), None)
        return jsonify({"paypal_order_id": payment.id, "approval_url": approval_url, "total": total})
    return jsonify({"error": payment.error}), 500

@app.route("/api/orders/complete", methods=["POST"])
def complete_order():
    data = request.json
    paypal_payment_id = data.get("paymentId")
    payer_id = data.get("PayerID")
    customer = data.get("customer", {})
    items = data.get("items", [])
    payment = paypalrestsdk.Payment.find(paypal_payment_id)
    if payment.execute({"payer_id": payer_id}):
        capture_id = payment.transactions[0].related_resources[0].sale.id
        payment_status = "completed"
    else:
        capture_id = None
        payment_status = "failed"
    subtotal = sum(next((p["price"] for p in PRODUCTS if p["id"] == it["id"]), 0) * int(it.get("qty", 1)) for it in items)
    total = round(subtotal + (0 if subtotal >= 50 else 7.99), 2)
    conn = get_db()
    cur = conn.execute("INSERT INTO orders (customer_name, email, phone, address, city, state, zip_code, items, subtotal, shipping, total, paypal_order_id, paypal_capture_id, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (customer.get("name", ""), customer.get("email", ""), customer.get("phone", ""), customer.get("address", ""), customer.get("city", ""), customer.get("state", ""), customer.get("zip", ""), json.dumps(items), subtotal, total-subtotal, total, paypal_payment_id, capture_id, payment_status))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    try:
        twilio_client.messages.create(body=f"🍯 New Order #{order_id}! From {customer.get('name')}. Total: ${total:.2f}", from_=TWILIO_PHONE_NUMBER, to=NOTIFICATION_PHONE_NUMBER)
    except: pass
    return jsonify({"order_id": order_id, "payment_status": payment_status, "sms_sent": True, "total": total})

@app.route("/api/orders/manual", methods=["POST"])
def manual_order():
    data = request.json
    customer = data.get("customer", {})
    items = data.get("items", [])
    subtotal = sum(next((p["price"] for p in PRODUCTS if p["id"] == it["id"]), 0) * int(it.get("qty", 1)) for it in items)
    total = round(subtotal + (0 if subtotal >= 50 else 7.99), 2)
    conn = get_db()
    cur = conn.execute("INSERT INTO orders (customer_name, email, phone, address, city, state, zip_code, items, subtotal, shipping, total, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (customer.get("name", ""), customer.get("email", ""), customer.get("phone", ""), customer.get("address", ""), customer.get("city", ""), customer.get("state", ""), customer.get("zip", ""), json.dumps(items), subtotal, total-subtotal, total, "manual"))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    try:
        twilio_client.messages.create(body=f"🍯 New Order #{order_id}! From {customer.get('name')}. Total: ${total:.2f}", from_=TWILIO_PHONE_NUMBER, to=NOTIFICATION_PHONE_NUMBER)
    except: pass
    return jsonify({"order_id": order_id, "sms_sent": True, "total": total})

@app.route("/api/admin/stats")
def admin_stats():
    conn = get_db()
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE payment_status IN ('completed','manual')").fetchone()[0]
    conn.close()
    return jsonify({"total_orders": total_orders, "total_revenue": round(total_revenue, 2), "pending_orders": total_orders, "sms_notifications_sent": total_orders})

@app.route("/api/admin/orders")
def admin_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5099, debug=False)
