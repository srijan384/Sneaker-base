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
# --- CART LOGIC ---

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    try:
        data = request.json
        
        # 1. Create the cart box if it doesn't exist
        if 'cart' not in session:
            session['cart'] = []
            
        # 2. Put the shoe inside the box
        session['cart'].append(data)
        
        # 3. SAVE IT! (This is the missing step usually)
        session.modified = True 
        
        print(f"Cart updated! Items: {len(session['cart'])}") # Debug print
        
        return jsonify({"count": len(session['cart']), "message": "Item added!"})

    except Exception as e:
        print("Error adding to cart:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/cart")
def view_cart():
    # 1. Get items from memory
    cart = session.get('cart', [])
    
    # 2. Calculate Total Price (Fixes the currency math)
    total = 0
    for item in cart:
        try:
            # Remove '₹', ',' and spaces to turn "₹12,749" into 12749
            clean_price = str(item['price']).replace('₹', '').replace(',', '').strip()
            total += int(float(clean_price))
        except:
            pass # If price is weird, skip it
            
    return render_template("cart.html", cart=cart, total=total, cart_count=len(cart))

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

        # --- FIX: CONVERT USD TO INR ---
        # 1. Get the price (defaults to 0 if missing)
        usd_price = product.get('price', 0)
        
        # 2. Multiply by 85 (Exchange Rate) and remove decimals
        inr_price = int(usd_price * 85)
        
        # 3. Update the product data with the new price
        product['price'] = f"{inr_price:,}" # Adds commas (e.g., "6,399")

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

# --- WISHLIST LOGIC ---

@app.route("/wishlist")
def wishlist():
    # Get the list of favorites from memory
    items = session.get('wishlist', [])
    return render_template("wishlist.html", products=items, cart_count=len(session.get('cart', [])))

# --- WISHLIST SAVING LOGIC ---

@app.route("/api/toggle_wishlist", methods=["POST"])
def toggle_wishlist():
    try:
        data = request.json
        
        # 1. Initialize Wishlist if it doesn't exist
        if 'wishlist' not in session:
            session['wishlist'] = []

        # 2. Check if item exists (by name)
        # We create a new list excluding the item to "remove" it
        existing = False
        new_wishlist = []
        
        for item in session['wishlist']:
            if item['name'] == data['name']:
                existing = True # It was found, so we skip adding it (Remove)
            else:
                new_wishlist.append(item) # Keep other items
        
        # 3. If it wasn't there, Add it
        if not existing:
            new_wishlist.append(data)
            action = "added"
        else:
            action = "removed"

        # 4. Save back to session
        session['wishlist'] = new_wishlist
        session.modified = True # IMPORTANT: Tells Flask to save the cookie
        
        print(f"Current Wishlist ({len(session['wishlist'])}): {session['wishlist']}") # Debug Print
        
        return jsonify({"status": action, "count": len(session['wishlist'])})

    except Exception as e:
        print("Error saving wishlist:", e)
        return jsonify({"error": str(e)}), 500
# --- FINAL RUN COMMAND (MUST BE LAST) ---
if __name__ == "__main__":
    app.run(debug=True, port=5000)