
import time
import random
from faker import Faker
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "sneaker-base-secret"
fake = Faker()

# ---------------- GLOBAL MEMORY ----------------
BLOCKED_IPS = {}

# ---------------- SNEAKER DATASET ----------------

BRANDS = ["Nike", "Adidas", "Puma", "New Balance", "Jordan"]

MODELS = [
"Air Max","Air Force","Air Jordan","Ultraboost",
"Dunk Low","Forum Low","Future Rider","RS-X",
"React Vision","Blazer Mid","NMD R1","Yeezy Boost",
"574 Classic","327 Runner","990 Sport"
]

IMAGES = [
"/static/assets/images/shoe1.webp",
"/static/assets/images/shoe2.webp",
"/static/assets/images/shoe3.webp",
"/static/assets/images/shoe4.webp",
"/static/assets/images/shoe5.webp"
]

SNEAKER_DB = []

for i in range(60):

    brand = random.choice(BRANDS)
    model = random.choice(MODELS)
    price = random.randint(7000,22000)

    SNEAKER_DB.append({
        "id": i,
        "name": f"{brand} {model}",
        "price": price,
        "image": random.choice(IMAGES)
    })


# ---------------- CLIENT IP ----------------
def get_client_ip():
    ip = request.remote_addr
    if ip in ("127.0.0.1","::1"):
        return "LOCAL_TEST_USER"
    return ip


# ---------------- HOME ----------------
@app.route("/")
def home():
    cart_count = len(session.get('cart',[]))
    return render_template("index.html", cart_count=cart_count)


# ---------------- PRODUCTS ----------------
@app.route("/products")
def products():

    ip = get_client_ip()
    cart_count = len(session.get('cart',[]))

    is_bot = ip in BLOCKED_IPS and BLOCKED_IPS[ip]["score"] >= 50
    page = int(request.args.get("page",1))
    per_page = 12

    # ---------------- BOT MODE ----------------
    if is_bot:

        print("🤖 BOT DETECTED → serving fake sneakers")

        fake_products = []

        start = (page-1) * per_page
        end = start + per_page

        for i in range(start,end):

            fake_price = random.randint(15000,85000)
            brand = random.choice(BRANDS)

            fake_products.append({
                "id": i,
                "name": f"{brand} {fake.word().capitalize()} {random.choice(['Air','Retro','Max','Pro'])}",
                "price": fake_price,
                "display_price": f"₹{fake_price:,}",
                "image": random.choice(IMAGES),
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

    category = request.args.get("category")
    brand = request.args.get("brand")

    data = SNEAKER_DB.copy()

    if category == "women":
        random.shuffle(data)

    elif category == "new":
        random.shuffle(data)

    real_products = []

    for item in data:

        name = item["name"]

        if brand and brand.lower() not in name.lower():
            continue

        real_products.append({
            "id": item["id"],
            "name": name,
            "price": item["price"],
            "display_price": f"₹{item['price']:,}",
            "image": item["image"],
            "status": random.choice(["IN STOCK","LOW STOCK"]),
            "btn_color": "#000",
            "btn_text": "ADD TO CART"
        })

    return render_template(
        "products.html",
        products=real_products,
        next_page=None,
        mode="human",
        cart_count=cart_count
    )


# ---------------- ADD TO CART ----------------
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():

    data = request.json

    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(data)
    session.modified = True

    return jsonify({
        "count": len(session['cart']),
        "message": "Item added!"
    })


# ---------------- CART PAGE ----------------
@app.route("/cart")
def view_cart():

    cart = session.get('cart',[])
    total = 0

    for item in cart:

        try:
            clean_price = str(item['price']).replace('₹','').replace(',','').strip()
            total += int(float(clean_price))
        except:
            pass

    return render_template(
        "cart.html",
        cart=cart,
        total=total,
        cart_count=len(cart)
    )


# ---------------- CLEAR CART ----------------
@app.route("/clear_cart")
def clear_cart():

    session.pop('cart',None)
    return redirect(url_for('view_cart'))


# ---------------- WISHLIST ----------------
@app.route("/wishlist")
def wishlist():

    items = session.get('wishlist',[])

    return render_template(
        "wishlist.html",
        products=items,
        cart_count=len(session.get('cart',[]))
    )


# ---------------- WISHLIST API ----------------
@app.route("/api/toggle_wishlist", methods=["POST"])
def toggle_wishlist():

    data = request.json

    if 'wishlist' not in session:
        session['wishlist'] = []

    existing = False
    new_list = []

    for item in session['wishlist']:

        if item['name'] == data['name']:
            existing = True
        else:
            new_list.append(item)

    if not existing:
        new_list.append(data)
        action = "added"
    else:
        action = "removed"

    session['wishlist'] = new_list
    session.modified = True

    return jsonify({
        "status": action,
        "count": len(session['wishlist'])
    })


# ---------------- BOT TRAP ----------------
@app.route("/api/v1/priority-access")
def trap():

    ip = get_client_ip()

    if ip not in BLOCKED_IPS:
        BLOCKED_IPS[ip] = {"score":0,"fake_served":0}

    BLOCKED_IPS[ip]["score"] += 100

    print("🚨 BOT MARKED:", ip)

    return jsonify({"error":"Invalid API Key"}),403


# ---------------- STATS ----------------
@app.route("/api/stats")
def stats():

    bot_count = len([
        ip for ip,data in BLOCKED_IPS.items()
        if data["score"] >= 50
    ])

    fake_count = sum(d["fake_served"] for d in BLOCKED_IPS.values())

    return jsonify({
        "active_bots": bot_count,
        "fake_records": fake_count
    })


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)

