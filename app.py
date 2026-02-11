import time
import random
from faker import Faker
import requests # Make sure you have this!
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "sneaker-base-secret"
fake = Faker()

# GLOBAL MEMORY
BLOCKED_IPS = {}

def get_client_ip():
    ip = request.remote_addr
    return "127.0.0.1" if ip == "::1" else ip

# --- ROUTES ---

@app.route("/")
def home():
    cart_count = len(session.get('cart', []))
    return render_template("index.html", cart_count=cart_count)

@app.route("/products")
def products():
    # ... (Keep your existing Products Logic here) ...
    # ... (I am hiding it to save space, but DO NOT DELETE IT) ...
    return render_template("products.html", products=[], next_page=None, mode="human", cart_count=0)


# --- CART LOGIC ---
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    # ... (Keep your existing Cart Logic) ...
    return jsonify({"count": 0, "message": "Item added!"})

@app.route("/cart")
def view_cart():
    # ... (Keep your existing Cart View Logic) ...
    return render_template("cart.html", cart=[], total=0, cart_count=0)

@app.route("/clear_cart")
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('view_cart'))


# --- NEW API ROUTES (MOVE THESE UP!) ---

@app.route("/api/sneakers")
def api_sneakers():
    try:
        # This fetches real data from the internet
        url = "https://dummyjson.com/products/category/mens-shoes"
        response = requests.get(url, timeout=5)
        data = response.json()

        sneakers = []
        for item in data.get("products", [])[:20]:
            sneakers.append({
                "id": item.get("id"),
                "name": item.get("title"),
                "price": item.get("price"),
                "image": item.get("thumbnail")
            })
        return jsonify(sneakers)

    except Exception as e:
        print("Sneaker API failed:", e)
        return jsonify([])

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    try:
        url = f"https://dummyjson.com/products/{product_id}"
        response = requests.get(url, timeout=5)
        product = response.json()
        return render_template("info.html", product=product)

    except Exception as e:
        print("Product fetch error:", e)
        return "Product not found", 404


# --- TRAP & STATS ---
@app.route("/api/v1/priority-access")
def trap():
    ip = get_client_ip()
    if ip not in BLOCKED_IPS: BLOCKED_IPS[ip] = {"score": 0, "fake_served": 0}
    BLOCKED_IPS[ip]["score"] += 100 
    return jsonify({"error": "Invalid API Key"}), 403

@app.route("/api/stats")
def stats():
    bot_count = len([ip for ip, data in BLOCKED_IPS.items() if data["score"] >= 50])
    fake_count = sum(d["fake_served"] for d in BLOCKED_IPS.values())
    return jsonify({"active_bots": bot_count, "fake_records": fake_count})


# --- FINAL RUN COMMAND (MUST BE LAST) ---
if __name__ == "__main__":
    app.run(debug=True, port=5000)