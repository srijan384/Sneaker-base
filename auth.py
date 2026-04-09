"""
auth.py — Sneaker Base Authentication
Handles: Email/Password, Google OAuth, Guest sessions
Database: MongoDB via pymongo
"""

import os
import re
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Blueprint, request, jsonify, session,
                   redirect, url_for, render_template)
from werkzeug.security import generate_password_hash, check_password_hash


# ── Google OAuth ──────────────────────────────────────────────────
try:
    from authlib.integrations.flask_client import OAuth
    OAUTH_OK = True
except ImportError:
    OAUTH_OK = False
    print("[AUTH] authlib not installed — Google OAuth disabled. Run: pip install authlib")

# ── MongoDB ───────────────────────────────────────────────────────
try:
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/")
    mongo     = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db        = mongo["sneaker_base"]
    users_col = db["users"]
    orders_col= db["orders"]
    # Ensure unique email index
    users_col.create_index("email", unique=True, sparse=True)
    MONGO_OK = True
    print("[AUTH] MongoDB connected ✅")
except Exception as e:
    MONGO_OK = False
    print(f"[AUTH] MongoDB unavailable ({e}) — auth routes will return errors ⚠️")

auth = Blueprint("auth", __name__)


# ================================================================
#  HELPERS
# ================================================================

def _serialize(doc: dict) -> dict:
    """Convert MongoDB doc to JSON-safe dict."""
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("password", None)       # never expose hash
    doc["_id"] = str(doc.get("_id", ""))
    return doc


def login_required(f):
    """Decorator — redirects to /login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def get_current_user() -> dict | None:
    """Return current user dict from session, or None."""
    uid = session.get("user_id")
    if not uid or not MONGO_OK:
        return None
    user = users_col.find_one({"user_id": uid})
    return _serialize(user)


def _start_session(user: dict):
    """Write user info into Flask session."""
    session.permanent = True
    session["user_id"]   = user["user_id"]
    session["user_name"] = user.get("name", "")
    session["user_email"]= user.get("email", "")
    session["is_guest"]  = user.get("is_guest", False)


# ================================================================
#  ROUTES — Pages
# ================================================================

@auth.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("auth.profile"))
    return render_template("login.html")


@auth.route("/profile")
@login_required
def profile():
    user = get_current_user()

    # Guest session — user won't be in MongoDB
    if user is None:
        user = {
            "user_id":       session.get("user_id", ""),
            "name":          session.get("user_name", "Guest"),
            "email":         session.get("user_email", ""),
            "picture":       None,
            "is_guest":      session.get("is_guest", True),
            "auth_provider": "guest",
        }

    cart     = session.get("cart", [])
    wishlist = session.get("wishlist", [])

    orders = []
    if MONGO_OK and not user.get("is_guest"):
        raw    = orders_col.find({"user_id": user["user_id"]}).sort("date", -1).limit(20)
        orders = [_serialize(o) for o in raw]

    return render_template("profile.html",
                           user=user,
                           cart=cart,
                           wishlist=wishlist,
                           orders=orders)

# ================================================================
#  ROUTES — Email / Password
# ================================================================

@auth.route("/auth/signup", methods=["POST"])
def signup():
    if not MONGO_OK:
        return jsonify({"success": False, "message": "Database unavailable"}), 503

    data  = request.get_json(force=True, silent=True) or {}
    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    pwd   = data.get("password", "")

    # Validate
    if not name:
        return jsonify({"success": False, "message": "Name is required"})
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "message": "Invalid email address"})
    if len(pwd) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters"})

    user_doc = {
        "user_id":       str(uuid.uuid4()),
        "name":          name,
        "email":         email,
        "password":      generate_password_hash(pwd),
        "auth_provider": "email",
        "is_guest":      False,
        "picture":       None,
        "created_at":    datetime.utcnow().isoformat(),
    }

    try:
        users_col.insert_one(user_doc)
    except DuplicateKeyError:
        return jsonify({"success": False, "message": "An account with this email already exists"})
    except Exception as e:
        return jsonify({"success": False, "message": "Could not create account"}), 500

    _start_session(user_doc)
    return jsonify({"success": True, "redirect": "/profile"})


@auth.route("/auth/login", methods=["POST"])
def login():
    if not MONGO_OK:
        return jsonify({"success": False, "message": "Database unavailable"}), 503

    data  = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    pwd   = data.get("password", "")

    user = users_col.find_one({"email": email, "auth_provider": "email"})
    if not user or not check_password_hash(user.get("password", ""), pwd):
        return jsonify({"success": False, "message": "Invalid email or password"})

    _start_session(user)
    return jsonify({"success": True, "redirect": "/profile"})


# ================================================================
#  ROUTES — Google OAuth
# ================================================================

def init_oauth(app):
    """Call this from app.py after creating Flask app."""
    if not OAUTH_OK:
        return None

    oauth = OAuth(app)
    google = oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


@auth.route("/auth/google")
def google_login():
    if not OAUTH_OK:
        return jsonify({"error": "Google OAuth not configured"}), 501
    from flask import current_app
    oauth = current_app.extensions.get("authlib.integrations.flask_client")
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth.route("/auth/google/callback")
def google_callback():
    if not OAUTH_OK:
        return redirect("/login?error=authlib_missing")
    if not MONGO_OK:
        return redirect("/login?error=mongodb_down")

    from flask import current_app
    oauth = current_app.extensions.get("authlib.integrations.flask_client")
    try:
        redirect_uri = "http://localhost:5001/auth/google/callback"
        token    = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo") or oauth.google.userinfo()
    except Exception as e:
        print(f"[AUTH] Google OAuth error: {e}")
        return redirect("/login?error=oauth_failed")

    email   = userinfo.get("email", "").lower()
    name    = userinfo.get("name", email.split("@")[0])
    picture = userinfo.get("picture")
    g_id    = userinfo.get("sub")

    existing = users_col.find_one({"email": email})
    if existing:
        users_col.update_one(
            {"email": email},
            {"$set": {"name": name, "picture": picture,
                      "auth_provider": "google", "google_id": g_id}}
        )
        user = users_col.find_one({"email": email})
    else:
        user = {
            "user_id":       str(uuid.uuid4()),
            "name":          name,
            "email":         email,
            "password":      None,
            "auth_provider": "google",
            "google_id":     g_id,
            "picture":       picture,
            "is_guest":      False,
            "created_at":    datetime.utcnow().isoformat(),
        }
        users_col.insert_one(user)

    _start_session(user)
    return redirect("/profile")
# ================================================================
#  ROUTES — Guest
# ================================================================

@auth.route("/auth/guest", methods=["POST"])
def guest_login():
    """Create a temporary guest session — no DB entry needed."""
    guest_id = "guest_" + str(uuid.uuid4())[:8]
    session["user_id"]   = guest_id
    session["user_name"] = "Guest"
    session["user_email"]= ""
    session["is_guest"]  = True
    return jsonify({"success": True, "redirect": "/"})


# ================================================================
#  ROUTES — Logout & Profile Update
# ================================================================

@auth.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")


@auth.route("/auth/update_profile", methods=["POST"])
@login_required
def update_profile():
    if not MONGO_OK:
        return jsonify({"success": False, "message": "Database unavailable"}), 503

    uid  = session.get("user_id")
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    pwd  = data.get("password", "")

    update = {}
    if name: update["name"] = name

    if pwd:
        if len(pwd) < 8:
            return jsonify({"success": False, "message": "Password must be at least 8 characters"})
        update["password"] = generate_password_hash(pwd)

    if not update:
        return jsonify({"success": False, "message": "Nothing to update"})

    users_col.update_one({"user_id": uid}, {"$set": update})
    if name: session["user_name"] = name

    return jsonify({"success": True})


# ================================================================
#  FORGOT PASSWORD (placeholder)
# ================================================================

@auth.route("/forgot-password")
def forgot_password():
    return render_template("login.html")