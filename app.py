import time
import random
from faker import Faker
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = "sneaker-base-secret"
fake = Faker()

# GLOBAL MEMORY (Stores detected bots)
BLOCKED_IPS = {}

def get_client_ip():
    ip = request.remote_addr
    return "127.0.0.1" if ip == "::1" else ip

# --- 1. HOME PAGE ---
@app.route("/")
def home():
    return render_template("index.html")

# --- 2. THE TRIPWIRE ---
@app.route("/api/v1/priority-access")
def trap():
    ip = get_client_ip()
    if ip not in BLOCKED_IPS:
        BLOCKED_IPS[ip] = {"score": 0, "fake_served": 0}
    
    BLOCKED_IPS[ip]["score"] += 100 
    print(f"🚨 TRAP HIT: {ip} flagged as BOT.")
    return jsonify({"error": "Invalid API Key"}), 403

# --- 3. PRODUCT PAGE ---
@app.route("/products")
def products():
    ip = get_client_ip()
    page = int(request.args.get("page", 1))
    
    is_bot = ip in BLOCKED_IPS and BLOCKED_IPS[ip]["score"] >= 50

    if is_bot:
        # === BOT MODE ===
        print(f"🤖 Serving FAKE DATA to {ip}")
        BLOCKED_IPS[ip]["fake_served"] += 12
        if page > 2: time.sleep(min(page * 0.5, 4)) 

        fake_products = []
        # UPDATED PATH: 'assets' (correct spelling)
        available_images = [f"shoe{i}.webp" for i in range(1, 11)] 

        for _ in range(12):
            img = random.choice(available_images)
            name = f"{fake.word().capitalize()} {random.choice(['Air', 'Jordan', 'Dunk', 'Yeezy'])}"
            fake_products.append({
                "name": name,
                "price": f"₹{random.randint(15000, 85000)}",
                # UPDATED PATH BELOW
                "image": f"/static/assets/images/{img}",
                "status": "IN STOCK",
                "btn_color": "#28a745",
                "btn_text": "ADD TO CART"
            })
            
        return render_template("products.html", products=fake_products, next_page=page+1, mode="bot")

    else:
        # === HUMAN MODE ===
        # UPDATED PATHS BELOW
        real_products = [
            {"name": "Nike Air Force 1", "price": "₹11,999", "image": "/static/assets/images/shoe1.webp", "status": "SOLD OUT", "btn_color": "#333", "btn_text": "SOLD OUT"},
            {"name": "CHUCK TAYLOR HEARTS", "price": "₹5,999", "image": "/static/assets/images/shoe2.webp", "status": "SOLD OUT", "btn_color": "#333", "btn_text": "SOLD OUT"},
            {"name": "New Balance 1906", "price": "₹16,499", "image": "/static/assets/images/shoe3.webp", "status": "SOLD OUT", "btn_color": "#333", "btn_text": "SOLD OUT"},
            {"name": "DUNK LOW RETRO", "price": "₹10,795", "image": "/static/assets/images/shoe4.webp", "status": "SOLD OUT", "btn_color": "#333", "btn_text": "SOLD OUT"},
        ]
        return render_template("products.html", products=real_products, next_page=None, mode="human")

# --- 4. DASHBOARD API ---
@app.route("/api/stats")
def stats():
    bot_count = len([ip for ip, data in BLOCKED_IPS.items() if data["score"] >= 50])
    fake_count = sum(d["fake_served"] for d in BLOCKED_IPS.values())
    return jsonify({"active_bots": bot_count, "fake_records": fake_count})

if __name__ == "__main__":
    app.run(debug=True, port=5000)