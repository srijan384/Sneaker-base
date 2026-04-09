import random
import time
import json
from datetime import datetime
import os
from faker import Faker
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
from auth import auth, init_oauth
from datetime import timedelta

app.register_blueprint(auth)
oauth = init_oauth(app)
app.permanent_session_lifetime = timedelta(days=30)
fake = Faker()

# ================================================================
#  REDIS — Persistent Bot Registry
# ================================================================
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    rdb = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    rdb.ping()
    REDIS_OK = True
    print("[BOT ENGINE] Redis connected ✅")
except Exception as e:
    rdb = None
    REDIS_OK = False
    print(f"[BOT ENGINE] Redis unavailable, falling back to memory ⚠️  ({e})")

# In-memory fallback
_MEM_REGISTRY = {}
_MEM_BLOCKED  = set()
_MEM_TRAP_LOG = []

# Redis key helpers
def _rkey_state(ip):  return f"bot:state:{ip}"
def _rkey_visits(ip): return f"bot:visits:{ip}"
def _rkey_blocked():  return "bot:blocked_ips"
def _rkey_traplog():  return "bot:trap_log"

# Thresholds
BOT_SCORE_SOFT  = 45
BOT_SCORE_HARD  = 70
MAX_VISITS_FAST = 30
FAST_WINDOW_SEC = 60

# ================================================================
#  BRAND / PRODUCT DATA
# ================================================================
BRAND_LOGOS = {
    "Nike":         "/static/assets/brands/nike.jpg",
    "Adidas":       "/static/assets/brands/adidas.jpg",
    "Puma":         "/static/assets/brands/puma.jpg",
    "Jordan":       "/static/assets/brands/jordan.jpg",
    "New Balance":  "/static/assets/brands/newbalance.jpg",
    "Asics":        "/static/assets/brands/asics.jpg",
    "Reebok":       "/static/assets/brands/reebok.jpg",
    "Converse":     "/static/assets/brands/converse.jpg",
    "Vans":         "/static/assets/brands/vans.jpg",
    "Under Armour": "/static/assets/brands/ua.jpg",
}
BRANDS = list(BRAND_LOGOS.keys())
BRAND_MODELS = {
    "Nike":         ["Air Max", "Air Force 1", "Dunk Low", "Blazer Mid", "React Vision"],
    "Adidas":       ["Ultraboost", "NMD R1", "Superstar", "Stan Smith", "Gazelle"],
    "Jordan":       ["Air Jordan 1", "Air Jordan 3", "Air Jordan 4", "Air Jordan Retro"],
    "Puma":         ["RS-X", "Future Rider", "Suede Classic", "Puma Runner"],
    "New Balance":  ["574 Classic", "327 Runner", "990 Sport"],
    "Asics":        ["Gel Kayano", "Gel Nimbus", "Gel Lyte"],
    "Reebok":       ["Club C", "Nano X", "Classic Leather"],
    "Converse":     ["Chuck Taylor", "Run Star", "All Star Lift"],
    "Vans":         ["Old Skool", "Sk8 Hi", "Authentic"],
    "Under Armour": ["HOVR Phantom", "Charged Rogue"],
}
BRAND_IMAGE_COUNT = {
    "Nike": 8, "Adidas": 10, "Asics": 10, "Converse": 10,
    "Jordan": 9, "New Balance": 8, "Puma": 5, "Reebok": 5,
    "Under Armour": 4, "Vans": 9,
}

SNEAKER_DB = []
for i in range(100):
    brand = random.choice(BRANDS)
    model = random.choice(BRAND_MODELS[brand])
    price = random.randint(6500, 22000)
    img_n = random.randint(1, BRAND_IMAGE_COUNT[brand])
    folder = brand.lower().replace(" ", "")
    SNEAKER_DB.append({
        "id": i, "brand": brand,
        "logo": BRAND_LOGOS[brand],
        "name": f"{brand} {model}",
        "price": price,
        "display_price": f"₹{price:,}",
        "image": f"/static/assets/images/{folder}/{folder}{img_n}.jpg",
    })

# ================================================================
#  BOT REGISTRY HELPERS
# ================================================================

def get_client_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ip = ip.split(",")[0].strip()
    if ip in ("127.0.0.1", "::1"):
        return "LOCAL_TEST_USER"
    return ip


def is_blocked(ip: str) -> bool:
    if REDIS_OK:
        return bool(rdb.sismember(_rkey_blocked(), ip))
    return ip in _MEM_BLOCKED


def flag_block(ip: str, score: int = 100):
    """Permanently block an IP — survives restarts via Redis."""
    if REDIS_OK:
        rdb.sadd(_rkey_blocked(), ip)
        raw   = rdb.get(_rkey_state(ip))
        state = json.loads(raw) if raw else _default_state()
        state["blocked"] = True
        state["flagged"] = True
        state["score"]   = score
        rdb.set(_rkey_state(ip), json.dumps(state), ex=86400 * 30)
    else:
        _MEM_BLOCKED.add(ip)


def get_bot_state(ip: str) -> dict:
    if REDIS_OK:
        raw = rdb.get(_rkey_state(ip))
        if raw:
            return json.loads(raw)
    else:
        if ip in _MEM_REGISTRY:
            return _MEM_REGISTRY[ip]
    return _default_state()


def save_bot_state(ip: str, state: dict):
    if REDIS_OK:
        rdb.set(_rkey_state(ip), json.dumps(state), ex=86400 * 30)
    else:
        _MEM_REGISTRY[ip] = state


def _default_state() -> dict:
    return {
        "score": 0, "flagged": False, "blocked": False,
        "first_seen": datetime.utcnow().isoformat(),
        "last_seen": None, "client_score": 0, "log": [],
    }


def append_trap_log(entry: dict):
    if REDIS_OK:
        rdb.lpush(_rkey_traplog(), json.dumps(entry))
        rdb.ltrim(_rkey_traplog(), 0, 499)
    else:
        _MEM_TRAP_LOG.insert(0, entry)
        if len(_MEM_TRAP_LOG) > 500:
            _MEM_TRAP_LOG.pop()


def get_trap_log(n: int = 50) -> list:
    if REDIS_OK:
        items = rdb.lrange(_rkey_traplog(), 0, n - 1)
        return [json.loads(x) for x in items]
    return _MEM_TRAP_LOG[:n]


def get_all_registry() -> list:
    result = []
    if REDIS_OK:
        keys = rdb.keys("bot:state:*")
        for k in keys:
            raw = rdb.get(k)
            if not raw:
                continue
            state = json.loads(raw)
            ip = k.replace("bot:state:", "")
            result.append({
                "ip": ip,
                "score":    state.get("score", 0),
                "flagged":  state.get("flagged", False),
                "blocked":  state.get("blocked", False),
                "last_seen": state.get("last_seen"),
                "events":   len(state.get("log", [])),
            })
    else:
        for ip, state in _MEM_REGISTRY.items():
            result.append({
                "ip": ip,
                "score":    state.get("score", 0),
                "flagged":  state.get("flagged", False),
                "blocked":  state.get("blocked", False),
                "last_seen": state.get("last_seen"),
                "events":   len(state.get("log", [])),
            })
    return result


def ua_bot_score(ua: str) -> int:
    ua = ua.lower()
    patterns = [
        ("python-requests", 40), ("python-urllib", 40), ("curl", 35),
        ("wget", 35), ("go-http-client", 30), ("java/", 25),
        ("scrapy", 50), ("axios", 20), ("httpx", 20),
        ("headlesschrome", 45), ("phantomjs", 50),
        ("bot", 30), ("crawler", 30), ("spider", 30),
        ("scraper", 40), ("selenium", 50),
    ]
    for pattern, pts in patterns:
        if pattern in ua:
            return pts
    return 0


def record_visit(ip: str) -> dict:
    state = get_bot_state(ip)
    now   = time.time()
    state["last_seen"] = datetime.utcnow().isoformat()

    if REDIS_OK:
        vkey = _rkey_visits(ip)
        rdb.zadd(vkey, {str(now): now})
        rdb.zremrangebyscore(vkey, 0, now - FAST_WINDOW_SEC)
        visit_count = rdb.zcard(vkey)
        rdb.expire(vkey, 3600)
    else:
        visit_count = 1

    if visit_count > MAX_VISITS_FAST:
        extra = min((visit_count - MAX_VISITS_FAST) * 3, 30)
        state["score"] = min(100, state["score"] + extra)
        state["log"].append({
            "event": "rapid_crawl", "visits": visit_count,
            "added_score": extra, "ts": datetime.utcnow().isoformat(),
        })

    ua     = request.headers.get("User-Agent", "")
    ua_pts = ua_bot_score(ua)
    if ua_pts and not any(e.get("event") == "ua_flag" for e in state["log"]):
        state["score"] = min(100, state["score"] + ua_pts)
        state["log"].append({
            "event": "ua_flag", "ua": ua,
            "added_score": ua_pts, "ts": datetime.utcnow().isoformat(),
        })

    if not request.headers.get("Accept-Language"):
        if not any(e.get("event") == "no_accept_lang" for e in state["log"]):
            state["score"] = min(100, state["score"] + 15)
            state["log"].append({
                "event": "no_accept_lang", "added_score": 15,
                "ts": datetime.utcnow().isoformat(),
            })

    if is_blocked(ip):
        state["blocked"] = True

    if state["score"] >= BOT_SCORE_SOFT:
        state["flagged"] = True
    if state["score"] >= BOT_SCORE_HARD:
        flag_block(ip, state["score"])
        state["blocked"] = True

    save_bot_state(ip, state)
    return state


def fake_product(p: dict) -> dict:
    orig   = p["price"]
    fake_p = int(orig * random.uniform(0.45, 0.65))
    return {
        **p,
        "price":              fake_p,
        "display_price":      f"₹{fake_p:,}",
        "original_price":     f"₹{orig:,}",
        "original_price_int": orig,
        "discount_pct":       random.randint(30, 55),
        "stock_left":         random.randint(1, 3),
    }


def generate_fake_sneakers(count: int = 24) -> list:
    """Generate fully fake sneaker listings for the bot trap page."""
    items = []
    for _ in range(count):
        brand      = random.choice(BRANDS)
        model      = random.choice(BRAND_MODELS[brand])
        orig_price = random.randint(6500, 22000)
        fake_price = int(orig_price * random.uniform(0.40, 0.65))
        img_n      = random.randint(1, BRAND_IMAGE_COUNT[brand])
        folder     = brand.lower().replace(" ", "")
        items.append({
            "id":             random.randint(1000, 9999),
            "name":           f"{brand} {model}",
            "brand":          brand,
            "display_price":  f"₹{fake_price:,}",
            "original_price": f"₹{orig_price:,}",
            "discount_pct":   random.randint(30, 55),
            "stock_left":     random.randint(1, 3),
            "image":          f"/static/assets/images/{folder}/{folder}{img_n}.jpg",
        })
    return items


# ================================================================
#  ROUTES
# ================================================================
from auth import login_required
@app.route("/")
@login_required
def home():
    ip    = get_client_ip()
    state = record_visit(ip)

    return render_template("index.html",
                           cart_count=len(session.get("cart", [])),
                           bot_flagged=state.get("flagged", False))

@app.route("/products")
def products():
    ip      = get_client_ip()
    state   = record_visit(ip)
    blocked = state.get("blocked", False)

    if blocked:
        append_trap_log({
            "event": "redirected_to_fake_products",
            "ip":    ip,
            "score": state.get("score", 0),
            "ts":    datetime.utcnow().isoformat(),
        })
        return redirect(url_for("fake_products"))

    page         = int(request.args.get("page", 1))
    per_page     = 12
    brand_filter = request.args.get("brand")
    category     = request.args.get("category")

    data = SNEAKER_DB.copy()
    if brand_filter:
        data = [s for s in data if brand_filter.lower() in s["brand"].lower()]
    if category == "new":
        random.shuffle(data)

    total     = len(data)
    start     = (page - 1) * per_page
    end       = start + per_page
    next_page = page + 1 if end < total else None

    return render_template("products.html", products=data[start:end],
                           next_page=next_page,
                           cart_count=len(session.get("cart", [])),
                           mode="human")
# ── Infinite fake products page ───────────────────────────────────
@app.route("/products/exclusive")
def fake_products():
    first_batch = generate_fake_sneakers(12)
    return render_template("bot_trap_products.html",
                           products=first_batch,
                           cart_count=len(session.get("cart", [])))

# ── JSON API for infinite scroll fake data ────────────────────────
@app.route("/api/fake_sneakers")
def api_fake_sneakers():
    count = min(int(request.args.get("count", 12)), 48)
    return jsonify(generate_fake_sneakers(count))

@app.route("/product/<int:product_id>")
def product_page(product_id):
    ip      = get_client_ip()
    state   = record_visit(ip)
    flagged = state.get("flagged", False)
    blocked = state.get("blocked", False) or is_blocked(ip)

    product = next((s for s in SNEAKER_DB if s["id"] == product_id), None)

    # Fake ID (1000-9999) from bot trap page — generate product on the fly
    if not product:
        if flagged or blocked:
            brand      = random.choice(BRANDS)
            model      = random.choice(BRAND_MODELS[brand])
            img_n      = random.randint(1, BRAND_IMAGE_COUNT[brand])
            folder     = brand.lower().replace(" ", "")
            orig_price = random.randint(6500, 22000)
            fake_price = int(orig_price * random.uniform(0.45, 0.65))
            product = {
                "id":             product_id,
                "brand":          brand,
                "name":           f"{brand} {model}",
                "price":          fake_price,
                "display_price":  f"₹{fake_price:,}",
                "original_price": f"₹{orig_price:,}",
                "discount_pct":   random.randint(30, 55),
                "stock_left":     random.randint(1, 3),
                "image": f"/static/assets/images/{folder}/{folder}{img_n}.jpg",
            }
            append_trap_log({
                "event":      "fake_product_page_served",
                "ip":         ip,
                "product_id": product_id,
                "score":      state.get("score", 0),
                "ts":         datetime.utcnow().isoformat(),
            })
            return render_template("trap_product.html",
                                   product=product,
                                   original_price=product["original_price"],
                                   discount_pct=product["discount_pct"],
                                   stock_left=product["stock_left"]), 200
        # Real user hitting a non-existent ID
        return "Product not found", 404

    # Real product exists — bot gets trap version, human gets real
    if flagged or blocked:
        fp = fake_product(product)
        append_trap_log({
            "event":      "trap_page_served",
            "ip":         ip,
            "product_id": product_id,
            "score":      state.get("score", 0),
            "ts":         datetime.utcnow().isoformat(),
        })
        return render_template("trap_product.html",
                               product=fp,
                               original_price=fp["original_price"],
                               discount_pct=fp["discount_pct"],
                               stock_left=fp["stock_left"]), 200

    # Clean human — show real product
    recommended = random.sample(SNEAKER_DB, 4)
    if "recent" not in session:
        session["recent"] = []
    session["recent"].append(product)
    session["recent"] = session["recent"][-4:]
    session.modified  = True

    return render_template("product.html", product=product,
                           recommended=recommended,
                           recent=session.get("recent", []),
                           cart_count=len(session.get("cart", [])))


# ── Honeytrap URLs ────────────────────────────────────────────────
@app.route("/trap/exclusive-access")
@app.route("/admin/export-users")
@app.route("/api/v1/all-products-dump")
@app.route("/api/v1/priority-access")
def honeytrap_url():
    ip    = get_client_ip()
    state = get_bot_state(ip)
    state["score"] = 100
    state["flagged"] = True
    state["blocked"] = True
    state["log"].append({
        "event": "honeytrap_url_hit", "path": request.path,
        "ts": datetime.utcnow().isoformat(),
    })
    save_bot_state(ip, state)
    flag_block(ip, 100)
    append_trap_log({
        "event": "honeytrap_url_hit", "ip": ip,
        "path": request.path, "ts": datetime.utcnow().isoformat(),
    })
    return jsonify({"status": "ok", "products": generate_fake_sneakers(10)}), 200


# ── Client-side signals ───────────────────────────────────────────
@app.route("/api/bot_signal", methods=["POST"])
def bot_signal():
    ip    = get_client_ip()
    state = get_bot_state(ip)

    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}

    client_score          = int(payload.get("botScore", 0))
    state["client_score"] = client_score
    combined              = int(state["score"] * 0.6 + client_score * 0.4)
    state["score"]        = min(100, combined)

    if payload.get("honeypotClicked"):
        state["score"]   = 100
        state["flagged"] = True
        state["blocked"] = True
        flag_block(ip, 100)

    if payload.get("webdriver") or payload.get("headless"):
        state["score"]   = min(100, state["score"] + 30)
        state["flagged"] = True

    if state["score"] >= BOT_SCORE_SOFT:
        state["flagged"] = True
    if state["score"] >= BOT_SCORE_HARD:
        flag_block(ip, state["score"])
        state["blocked"] = True

    state["log"].append({
        "event": "client_signal",
        "client_score":  client_score,
        "combined_score": state["score"],
        "ts": datetime.utcnow().isoformat(),
    })
    save_bot_state(ip, state)

    return jsonify({
        "status":   "ok",
        "score":    state["score"],
        "flagged":  state["flagged"],
        "redirect": state["flagged"],
    }), 200


# ── Trap capture ──────────────────────────────────────────────────
@app.route("/api/bot_trap_capture", methods=["POST"])
def bot_trap_capture():
    ip = get_client_ip()
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}
    entry = {"ip": ip, "ts": datetime.utcnow().isoformat(), **payload}
    append_trap_log(entry)
    print(f"[BOT TRAP] {entry}")
    return jsonify({"status": "captured"}), 200


# ── SOC data ──────────────────────────────────────────────────────
@app.route("/api/soc_data")
def soc_data():
    blocked_count = rdb.scard(_rkey_blocked()) if REDIS_OK else len(_MEM_BLOCKED)
    registry      = get_all_registry()
    trap_log      = get_trap_log(500)
    return jsonify({
        "total_ips":   len(registry),
        "flagged":     sum(1 for r in registry if r["flagged"]),
        "blocked":     blocked_count,
        "trap_events": len(trap_log),
        "registry":    registry,
        "trap_log":    get_trap_log(50),
        "redis_ok":    REDIS_OK,
    })


# ── Debug routes ──────────────────────────────────────────────────
@app.route("/debug/flag-me")
def debug_flag_me():
    ip    = get_client_ip()
    state = get_bot_state(ip)
    state["score"]   = 100
    state["flagged"] = True
    state["blocked"] = True
    save_bot_state(ip, state)
    flag_block(ip, 100)
    return jsonify({"status": "flagged", "ip": ip,
                    "next": "Visit /products or /product/1"})


@app.route("/debug/unblock-me")
def debug_unblock_me():
    ip = get_client_ip()
    if REDIS_OK:
        rdb.srem(_rkey_blocked(), ip)
        rdb.delete(_rkey_state(ip))
        rdb.delete(_rkey_visits(ip))
    else:
        _MEM_BLOCKED.discard(ip)
        _MEM_REGISTRY.pop(ip, None)
    return jsonify({"status": "unblocked", "ip": ip})


@app.route("/api/sneakers")
def api_sneakers():
    ip      = get_client_ip()
    state   = record_visit(ip)
    flagged = state.get("flagged", False)
    sample  = random.sample(SNEAKER_DB, 4)
    if flagged:
        sample = [fake_product(s) for s in sample]
    return jsonify([{
        "id":            s["id"],
        "name":          s["name"],
        "price":         s["display_price"],   # was s["display_price"] — keep
        "display_price": s["display_price"],   # add this so templates work
        "image":         s["image"],
    } for s in sample])


# ── Fix 3: add_to_cart also saves id ─────────────────────────────
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.json
    if "cart" not in session:
        session["cart"] = []
    session["cart"].append({
        "name":  data.get("name", ""),
        "price": data.get("price", ""),
        "image": data.get("image", ""),
        "size":  data.get("size", ""),
        "id":    data.get("id", ""),   # save id so cart items are also clickable
    })
    session.modified = True
    return jsonify({
        "count":   len(session["cart"]),
        "message": "Item added!",
        "success": True
    })


@app.route("/cart")
def view_cart():
    cart  = session.get("cart", [])
    total = 0
    for item in cart:
        try:
            total += int(str(item["price"]).replace("₹", "").replace(",", ""))
        except Exception:
            pass
    return render_template("cart.html", cart=cart, total=total, cart_count=len(cart))

@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():
    item_id = request.form.get("id")

    cart = session.get("cart", [])
    cart = [item for item in cart if str(item.get("id")) != str(item_id)]

    session["cart"] = cart
    session.modified = True

    return redirect("/cart")

@app.route("/wishlist")
def wishlist_page():
    items = session.get("wishlist", [])
    return render_template("wishlist.html", products=items,
                           cart_count=len(session.get("cart", [])))

@app.route('/api/toggle_wishlist', methods=['POST'])
def toggle_wishlist():
    data = request.json

    if "wishlist" not in session:
        session["wishlist"] = []

    wishlist = session["wishlist"]

    # Check if item already exists → remove it
    for item in wishlist:
        if item.get("id") == data.get("id"):
            wishlist.remove(item)
            session.modified = True
            return jsonify({"status": "removed"})

    # Add new item (WITH ID 🔥)
    wishlist.append({
        "name": data.get("name"),
        "price": data.get("price"),
        "image": data.get("image"),
        "size": data.get("size"),
        "id": data.get("id")   # ⭐ MOST IMPORTANT LINE
    })

    session.modified = True
    return jsonify({"status": "added"})

@app.route("/soc")
def soc_dashboard():
    return render_template("soc_dashboard.html")


@app.route("/health")
def health():
    return {"status": "ok", "redis": REDIS_OK}

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session.pop("cart", None)
    session.modified = True
    return redirect(url_for("view_cart"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)


@app.context_processor
def inject_user():
    from auth import get_current_user
    user = get_current_user()
    return {"current_user": user,
            "is_logged_in": user is not None and not user.get("is_guest"),
            "is_guest": user is not None and user.get("is_guest", False)}