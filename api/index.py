from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/api/products")
def get_products():
    return jsonify([
        {"id": "wildflower-16", "name": "Wildflower Honey", "size": "16 oz", "price": 14.99, "image": "🌸"},
        {"id": "clover-16", "name": "Clover Honey", "size": "16 oz", "price": 12.99, "image": "🍀"},
        {"id": "manuka-8", "name": "Mānuka Honey", "size": "8 oz", "price": 29.99, "image": "🌿"},
        {"id": "gift-box", "name": "Honey Gift Box", "size": "3×8 oz", "price": 39.99, "image": "🎁"}
    ])

@app.route("/api/health")
def health(): return "OK"
