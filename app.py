import os
import sqlite3
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from twilio.rest import Client as TwilioClient
import paypalrestsdk

# ── Configuration ──────────────────────────────────────────────────────────────────────
PAYPAL_CLIENT_ID = "AbeuVcyPADfETQPoMFsoonAhho32d2Ejx1oBelG2vQuGi8D4RmInNhRcpXoQoONphngmYeCXhtTtQgIYVM"
PAYPAL_SECRET = "EMZu-ww25716GB6lh4_b-sEZYMiMo_Gn3u_-Are7mxHboXD5q1uNCK-OtmWuufFZ8iXlX0V47Uf9fOjfd"
TWILIO_ACCOUNT_SID = "AC1aface281d36d9fd9087c7"
TWILIO_AUTH_TOKEN = "8514c1e9e2a3c0938e4f0fb8e7"
TWILIO_PHONE_NUMBER = "+18556838803"
NOTIFICATION_PHONE_NUMBER = "+13184231053"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")

# ── PayPal (LIVE) ──────────────────────────────────────────────────────────
paypalrestsdk.configure({
    "mode": "live",
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET,
})

# ── Twilio ─────────────────────────────────────────────────────────────────

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ── Database ─────────────────────────────────────────────────────────────────
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

init_db()

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/admin")
def admin():
    return send_from_directory("static", "admin.html")

@app.route("/success")
def success_page():
    return send_from_directory("static", "success.html")

@app.route("/game")
def game_page():
    return send_from_directory("static", "game.html")

# ── API: Products ──────────────────────────────────────────────────────────
PRODUCTS = [
    {"id": "wildflower-16", "name": "Wildflower Honey", "size": "16 oz", "price": 14.99,
     "description": "A beautiful blend of wildflower nectars with rich, complex flavor.",
     "image": "🌸"},
    {"id": "clover-16", "name": "Clover Honey", "size": "16 oz", "price": 12.99,
     "description": "Classic light & sweet clover honey, perfect for everyday use.",
     "image": "🍀"},
    {"id": "manuka-8", "name": "Mānuka Honey", "size": "8 oz", "price": 29.99,
     "description": "Premium Mānuka honey with exceptional antibacterial properties.",
     "image": "🌿"},
    {"id": "buckwheat-16", "name": "Buckwheat Honey", "size": "16 oz", "price": 16.99,
     "description": "Dark, bold buckwheat honey—rich in antioxidants.",
     "image": "🌾"},
    {"id": "orange-16", "name": "Orange Blossom Honey", "size": "16 oz", "price": 15.99,
     "description": "Delicate citrus notes from orange blossom nectar.",
     "image": "🍊"},
    {"id": "gift-box", "name": "Honey Gift Box", "size": "3×8 oz", "price": 39.99,
     "description": "A curated sampler of three artisan honeys in a gift box.",
     "image": "🎁"},
]

@app.route("/api/products")
def get_products():
    return jsonify(PRODUCTS)

# ── API: Create PayPal Order ───────────────────────────────────────────────
@app.route("/api/orders/create-paypal", methods=["POST"])
def create_paypal_order():
    data = request.json
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "No items in cart"}), 400

    subtotal = 0
    line_items = []
    for item in items:
        product = next((p for p in PRODUCTS if p["id"] == item["id"]), None)
        if not product:
            return jsonify({"error": f"Unknown product {item['id']}"}), 400
        qty = int(item.get("qty", 1))
        subtotal += product["price"] * qty
        line_items.append({
            "name": product["name"],
            "unit_amount": {"currency_code": "USD", "value": f"{product['price']:.2f}"},
            "quantity": str(qty),
        })

    shipping = 0 if subtotal >= 50 else 7.99
    total = round(subtotal + shipping, 2)

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": request.host_url + "success",
            "cancel_url": request.host_url,
        },
        "transactions": [{
            "item_list": {"items": line_items},
            "amount": {
                "total": f"{total:.2f}",
                "currency": "USD",
                "details": {
                    "subtotal": f"{subtotal:.2f}",
                    "shipping": f"{shipping:.2f}",
                },
            },
            "description": "Golden Hive Honey Co. Order",
        }],
    })

    if payment.create():
        approval_url = next(
            (link.href for link in payment.links if link.rel == "approval_url"), None
        )
        return jsonify({
            "paypal_order_id": payment.id,
            "approval_url": approval_url,
            "total": total,
            "subtotal": subtotal,
            "shipping": shipping,
        })
    else:
        return jsonify({"error": payment.error}), 500

# ── API: Capture / Complete Order ──────────────────────────────────────────
@app.route("/api/orders/complete", methods=["POST"])
def complete_order():
    data = request.json
    paypal_payment_id = data.get("paymentId")
    payer_id = data.get("PayerID")
    customer = data.get("customer", {})
    items = data.get("items", [])

    # Execute PayPal payment
    payment = paypalrestsdk.Payment.find(paypal_payment_id)
    if payment.execute({"payer_id": payer_id}):
        capture_id = payment.transactions[0].related_resources[0].sale.id
        payment_status = "completed"
    else:
        capture_id = None
        payment_status = "failed"

    subtotal = sum(
        next((p["price"] for p in PRODUCTS if p["id"] == it["id"]), 0) * int(it.get("qty", 1))
        for it in items
    )
    shipping = 0 if subtotal >= 50 else 7.99
    total = round(subtotal + shipping, 2)

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO orders
            (customer_name, email, phone, address, city, state, zip_code,
             items, subtotal, shipping, total,
             paypal_order_id, paypal_capture_id, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer.get("name", ""),
        customer.get("email", ""),
        customer.get("phone", ""),
        customer.get("address", ""),
        customer.get("city", ""),
        customer.get("state", ""),
        customer.get("zip", ""),
        json.dumps(items),
        subtotal, shipping, total,
        paypal_payment_id, capture_id, payment_status,
    ))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Send SMS notification
    sms_sent = False
    try:
        item_summary = ", ".join(
            f"{it.get('qty',1)}× {next((p['name'] for p in PRODUCTS if p['id']==it['id']),'?')}"
            for it in items
        )
        msg_body = (
            f"🍯 New Honey Order #{order_id}!\n"
            f"Customer: {customer.get('name','N/A')}\n"
            f"Items: {item_summary}\n"
            f"Total: ${total:.2f}\n"
            f"Ship to: {customer.get('city','')}, {customer.get('state','')}"
        )
        twilio_client.messages.create(
            body=msg_body,
            from_=TWILIO_PHONE_NUMBER,
            to=NOTIFICATION_PHONE_NUMBER,
        )
        sms_sent = True
        conn = get_db()
        conn.execute("UPDATE orders SET sms_sent=1 WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"SMS send error: {e}")

    return jsonify({
        "order_id": order_id,
        "payment_status": payment_status,
        "sms_sent": sms_sent,
        "total": total,
    })

# ── API: Manual / Test Order (no PayPal) ───────────────────────────────────
@app.route("/api/orders/manual", methods=["POST"])
def manual_order():
    data = request.json
    customer = data.get("customer", {})
    items = data.get("items", [])

    subtotal = sum(
        next((p["price" ] for p in PRODUCTS if p["id"] == it["id"]), 0) * int(it.get("qty", 1))
        for it in items
    )
    shipping = 0 if subtotal >= 50 else 7.99
    total = round(subtotal + shipping, 2)

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO orders
            (customer_name, email, phone, address, city, state, zip_code,
             items, subtotal, shipping, total,
             payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer.get("name", ""),
        customer.get("email", ""),
        customer.get("phone", ""),
        customer.get("address", ""),
        customer.get("city", ""),
        customer.get("state", ""),
        customer.get("zip", ""),
        json.dumps(items),
        subtotal, shipping, total,
        "manual",
    ))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Send SMS notification
    sms_sent = False
    try:
        item_summary = ", ".join(
            f"{it.get('qty',1)}× {next((p['name'] for p in PRODUCTS if p['id']==it['id']),'?')}"
            for it in items
        )
        msg_body = (
            f"🍯 New Honey Order #{order_id}!\n"
            f"Customer: {customer.get('name','N/A')}\n"
            f"Items: {item_summary}\n"
            f"Total: ${total:.2f}\n"
            f"Ship to: {customer.get('city','')}, {customer.get('state','')}"
        )
        twilio_client.messages.create(
            body=msg_body,
            from_=TWILIO_PHONE_NUMBER,
            to=NOTIFICATION_PHONE_NUMBER,
        )
        sms_sent = True
        conn = get_db()
        conn.execute("UPDATE orders SET sms_sent=1 WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"SMS send error: {e}")

    return jsonify({
        "order_id": order_id,
        "payment_status": "manual",
        "sms_sent": sms_sent,
        "total": total,
    })

# ── API: Admin – List Orders ───────────────────────────────────────────
@app.route("/api/admin/orders")
def admin_orders():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    orders = []
    for r in rows:
        orders.append({
            "id": r["id"],
            "customer_name": r["customer_name"],
            "email": r["email"],
            "phone": r["phone"],
            "address": r["address"],
            "city": r["city"],
            "state": r["state"],
            "zip_code": r["zip_code"],
            "items": json.loads(r["items"]) if r["items"] else [],
            "subtotal": r["subtotal"],
            "shipping": r["shipping"],
            "total": r["total"],
            "paypal_order_id": r["paypal_order_id"],
            "paypal_capture_id": r["paypal_capture_id"],
            "payment_status": r["payment_status"],
            "order_status": r["order_status"],
            "sms_sent": bool(r["sms_sent"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return jsonify(orders)

# ── API: Admin – Update Order Status ─────────────────────────────────────────
@app.route("/api/admin/orders/<int:order_id>/status", methods=["PATCH"])
def update_order_status(order_id):
    data = request.json
    new_status = data.get("order_status")
    if new_status not in ("new", "processing", "shipped", "delivered", "cancelled"):
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE orders SET order_status=?, updated_at=datetime('now') WHERE id=?",
        (new_status, order_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "order_id": order_id, "order_status": new_status})

# ── API: Dashboard Stats ────────────────────────────────────────────────────
@app.route("/api/admin/stats")
def admin_stats():
    conn = get_db()
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE payment_status IN ('completed','manual')").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM orders WHERE order_status='new'").fetchone()[0]
    sms_count = conn.execute("SELECT COUNT(*) FROM orders WHERE sms_sent=1").fetchone()[0]
    conn.close()
    return jsonify({
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "pending_orders": pending,
        "sms_notifications_sent": sms_count,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5099, debug=False)
