import time
import random
from faker import Faker
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "sneaker-base-secret"
fake = Faker()

# GLOBAL MEMORY
BLOCKED_IPS = {}

# ---------------- FIX 1: SAME USER FOR LOCALHOST ----------------
def get_client_ip():
    ip = request.remote_addr
    if ip in ("127.0.0.1", "::1"):
        return "LOCAL_TEST_USER"
    return ip


# ---------------- HOME ----------------
@app.route("/")
def home():
    cart_count = len(session.get('cart', []))
    return render_template("index.html", cart_count=cart_count)


# ---------------- PRODUCTS (HONEYPOT SWITCH) ----------------
@app.route("/products")
def products():
    ip = get_client_ip()
    cart_count = len(session.get('cart', []))

    is_bot = ip in BLOCKED_IPS and BLOCKED_IPS[ip]["score"] >= 50
    page = int(request.args.get("page", 1))
    per_page = 12

    # ---------------- BOT MODE ----------------
    if is_bot:
        print("🤖 Serving FAKE PRODUCTS PAGE", page, "to", ip)

        try:
            # fetch real api
            url = "https://dummyjson.com/products/category/mens-shoes"
            response = requests.get(url, timeout=5)
            data = response.json().get("products", [])

        except:
            data = []

        fake_products = []

        start = (page-1) * per_page
        end = start + per_page

        for i in range(start, min(end, start + per_page)):
            base = random.choice(data) if data else {}

            fake_price = random.randint(15000, 85000)
            brand = random.choice(["Nike", "Adidas", "Puma", "New Balance", "Jordan"])

            fake_products.append({
                "name": f"{brand} {fake.word().capitalize()} {random.choice(['Air','Retro','Pro','Max'])}",
                "price": fake_price,
                "display_price": f"₹{fake_price:,}",
                "image": base.get("thumbnail", "/static/assets/images/shoe1.webp"),
                "status": random.choice(["IN STOCK","LOW STOCK","ONLY 1 LEFT"]),
                "btn_color": "#28a745",
                "btn_text": "ADD TO CART"
            })

        next_page = page + 1

        return render_template(
            "products.html",
            products=fake_products,
            next_page=next_page,
            mode="bot",
            cart_count=cart_count
        )

    # ---------------- HUMAN MODE ----------------
    real_products = [
        {"name":"Nike Air Force 1","price":11999,"display_price":"₹11,999","image":"/static/assets/images/shoe1.webp","status":"SOLD OUT","btn_color":"#333","btn_text":"SOLD OUT"},
        {"name":"New Balance 1906","price":16499,"display_price":"₹16,499","image":"/static/assets/images/shoe2.webp","status":"SOLD OUT","btn_color":"#333","btn_text":"SOLD OUT"},
        {"name":"Dunk Low Retro","price":10795,"display_price":"₹10,795","image":"/static/assets/images/shoe3.webp","status":"SOLD OUT","btn_color":"#333","btn_text":"SOLD OUT"}
    ]

    return render_template(
        "products.html",
        products=real_products,
        next_page=None,
        mode="human",
        cart_count=cart_count
    )

# ---------------- CART ----------------
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.json
    if 'cart' not in session:
        session['cart'] = []
    session['cart'].append(data)
    session.modified = True
    return jsonify({"count": len(session['cart']), "message": "Item added!"})


@app.route("/cart")
def view_cart():
    cart = session.get('cart', [])
    total = 0
    for item in cart:
        try:
            clean_price = str(item['price']).replace('₹','').replace(',','').strip()
            total += int(float(clean_price))
        except:
            pass
    return render_template("cart.html", cart=cart, total=total, cart_count=len(cart))


@app.route("/clear_cart")
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('view_cart'))


# ---------------- REAL API ----------------
@app.route("/api/sneakers")
def api_sneakers():
    try:
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

    except:
        return jsonify([])


# ---------------- TRAP ----------------
@app.route("/api/v1/priority-access")
def trap():
    ip = get_client_ip()
    if ip not in BLOCKED_IPS:
        BLOCKED_IPS[ip] = {"score": 0, "fake_served": 0}

    BLOCKED_IPS[ip]["score"] += 100
    print("🚨 BOT MARKED:", ip)

    return jsonify({"error": "Invalid API Key"}), 403


# ---------------- STATS ----------------
@app.route("/api/stats")
def stats():
    bot_count = len([ip for ip,data in BLOCKED_IPS.items() if data["score"]>=50])
    fake_count = sum(d["fake_served"] for d in BLOCKED_IPS.values())
    return jsonify({"active_bots":bot_count,"fake_records":fake_count})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)