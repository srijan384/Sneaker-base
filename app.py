import random
from faker import Faker
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = "sneaker-base-secret"
fake = Faker()

# ---------------- GLOBAL MEMORY ----------------
BLOCKED_IPS = {}

# ---------------- BRAND LOGOS ----------------
BRAND_LOGOS = {
    "Nike": "/static/assets/brands/nike.jpg",
    "Adidas": "/static/assets/brands/adidas.jpg",
    "Puma": "/static/assets/brands/puma.jpg",
    "Jordan": "/static/assets/brands/jordan.jpg",
    "New Balance": "/static/assets/brands/newbalance.jpg",
    "Asics": "/static/assets/brands/asics.jpg",
    "Reebok": "/static/assets/brands/reebok.jpg",
    "Converse": "/static/assets/brands/converse.jpg",
    "Vans": "/static/assets/brands/vans.jpg",
    "Under Armour": "/static/assets/brands/ua.jpg"
}

# ---------------- BRANDS ----------------
BRANDS = list(BRAND_LOGOS.keys())

# ---------------- BRAND MODELS ----------------
BRAND_MODELS = {

"Nike":[
"Air Max","Air Force 1","Dunk Low","Blazer Mid","React Vision"
],

"Adidas":[
"Ultraboost","NMD R1","Superstar","Stan Smith","Gazelle"
],

"Jordan":[
"Air Jordan 1","Air Jordan 3","Air Jordan 4","Air Jordan Retro"
],

"Puma":[
"RS-X","Future Rider","Suede Classic","Puma Runner"
],

"New Balance":[
"574 Classic","327 Runner","990 Sport"
],

"Asics":[
"Gel Kayano","Gel Nimbus","Gel Lyte"
],

"Reebok":[
"Club C","Nano X","Classic Leather"
],

"Converse":[
"Chuck Taylor","Run Star","All Star Lift"
],

"Vans":[
"Old Skool","Sk8 Hi","Authentic"
],

"Under Armour":[
"HOVR Phantom","Charged Rogue"
]

}

# ---------------- IMAGE COUNTS ----------------
BRAND_IMAGE_COUNT = {
"Nike":8,
"Adidas":10,
"Asics":10,
"Converse":10,
"Jordan":9,
"New Balance":8,
"Puma":5,
"Reebok":5,
"Under Armour":4,
"Vans":9
}

# ---------------- DATASET ----------------
SNEAKER_DB = []

for i in range(100):

    brand = random.choice(BRANDS)
    model = random.choice(BRAND_MODELS[brand])
    price = random.randint(6500,22000)

    img_number = random.randint(1, BRAND_IMAGE_COUNT[brand])
    folder = brand.lower().replace(" ","")

    image = f"/static/assets/images/{folder}/{folder}{img_number}.jpg"

    SNEAKER_DB.append({
        "id": i,
        "brand": brand,
        "logo": BRAND_LOGOS.get(brand),
        "name": f"{brand} {model}",
        "price": price,
        "display_price": f"₹{price:,}",
        "image": image
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

    page = int(request.args.get("page",1))
    per_page = 12

    category = request.args.get("category")
    brand_filter = request.args.get("brand")

    data = SNEAKER_DB.copy()

    if brand_filter:
        data = [shoe for shoe in data if brand_filter.lower() in shoe["brand"].lower()]

    if category == "new":
        random.shuffle(data)

    total = len(data)

    start = (page-1)*per_page
    end = start+per_page

    data = data[start:end]

    next_page = page+1 if end < total else None

    return render_template(
        "products.html",
        products=data,
        next_page=next_page,
        cart_count=len(session.get('cart',[])),
        mode="human"
    )


# ---------------- PRODUCT PAGE ----------------
@app.route("/product/<int:product_id>")
def product_page(product_id):

    product = None

    for item in SNEAKER_DB:
        if item["id"] == product_id:
            product = item
            break

    if not product:
        return "Product not found",404

    recommended = random.sample(SNEAKER_DB,4)

    if "recent" not in session:

        session["recent"] = []

    session["recent"].append(product)

    session["recent"] = session["recent"][-4:]

    session.modified = True

    return render_template(
    "product.html",
    product=product,
    recommended=recommended,
    recent=session.get("recent",[]),
    cart_count=len(session.get('cart', []))
)
    


# ---------------- HOMEPAGE API ----------------
@app.route("/api/sneakers")
def api_sneakers():

    sample = random.sample(SNEAKER_DB,4)

    sneakers=[]

    for item in sample:
        sneakers.append({
            "id": item["id"],
            "name": item["name"],
            "price": item["display_price"],
            "image": item["image"]
        })

    return jsonify(sneakers)


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
        "message":"Item added!"
    })


# ---------------- TOGGLE WISHLIST ----------------
@app.route("/api/toggle_wishlist", methods=["POST"])
def toggle_wishlist():

    data = request.json

    if 'wishlist' not in session:
        session['wishlist'] = []

    existing=False
    new_list=[]

    for item in session['wishlist']:

        if item['name']==data['name']:
            existing=True
        else:
            new_list.append(item)

    if not existing:
        new_list.append(data)
        action="added"
    else:
        action="removed"

    session['wishlist']=new_list
    session.modified=True

    return jsonify({
        "status":action,
        "count":len(session['wishlist'])
    })


# ---------------- CART PAGE ----------------
@app.route("/cart")
def view_cart():

    cart=session.get('cart',[])
    total=0

    for item in cart:
        try:
            clean_price=str(item['price']).replace('₹','').replace(',','')
            total+=int(clean_price)
        except:
            pass

    return render_template(
        "cart.html",
        cart=cart,
        total=total,
        cart_count=len(cart)
    )


# ---------------- WISHLIST PAGE ----------------
@app.route("/wishlist")
def wishlist_page():

    items=session.get('wishlist',[])

    return render_template(
        "wishlist.html",
        products=items,
        cart_count=len(session.get('cart',[]))
    )


# ---------------- SOC DASHBOARD ----------------
@app.route("/soc")
def soc_dashboard():
    return render_template("soc_dashboard.html")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)