// ── Toast helper ─────────────────────────────────────────
function showToast(title, name, image) {
    var toast   = document.getElementById("cart-toast");
    var titleEl = document.getElementById("toast-title") || document.querySelector(".toast-title");
    var nameEl  = document.getElementById("toast-name");
    var imgEl   = document.getElementById("toast-img");
    if (!toast) return;
    if (titleEl) titleEl.textContent = title || "✓ Done";
    if (nameEl)  nameEl.textContent  = name  || "";
    if (imgEl && image) imgEl.src    = image;
    toast.classList.add("show");
    setTimeout(function() { toast.classList.remove("show"); }, 3000);
}

// ── Cart counter ──────────────────────────────────────────
function updateCartCounter(count) {
    var counter = document.getElementById("cart-count");
    if (counter) {
        counter.style.display = "inline";
        counter.innerText = count;
    } else {
        var icon = document.querySelector(".fa-shopping-cart");
        if (icon) {
            var span       = document.createElement("span");
            span.id        = "cart-count";
            span.style     = "background:black;color:white;border-radius:50%;padding:2px 6px;font-size:12px;vertical-align:top;";
            span.innerText = count;
            icon.parentElement.appendChild(span);
        }
    }
}

// ── Add to cart (used on home / products pages) ───────────
function addToCart(name, price, image) {
    fetch('/add_to_cart', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ name: name, price: price, image: image })
    })
    .then(function(res) {
        if (!res.ok) throw new Error("Server error " + res.status);
        return res.json();
    })
    .then(function(data) {
        updateCartCounter(data.count);
        showToast("✓ Added to cart", name, image);
    })
    .catch(function(err) {
        console.error("Cart error:", err);
        showToast("⚠ Could not add", "Please try again", "");
    });
}

// ── Wishlist toggle ───────────────────────────────────────
function toggleHeart(btn, name, price, image) {
    btn.classList.toggle("active");
    var icon = btn.querySelector("i");
    if (icon) icon.style.color = btn.classList.contains("active") ? "#e53935" : "#ccc";
    fetch('/api/toggle_wishlist', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ name: name, price: price, image: image })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        showToast(
            data.status === 'added' ? '♡ Saved to wishlist' : '♡ Removed from wishlist',
            name, image
        );
    })
    .catch(function() {});
}

// ── Load sneakers on home page ────────────────────────────
async function loadSneakers() {
    var grid = document.getElementById("product-grid");
    if (!grid) return;

    // Skeleton
    grid.innerHTML = [1,2,3,4].map(function() { return (
        '<div class="product">' +
          '<div class="skel-base" style="height:200px;border-radius:0;margin:0;"></div>' +
          '<div style="padding:14px 16px 16px;">' +
            '<div class="skel-base" style="height:16px;width:70%;margin-bottom:8px;"></div>' +
            '<div class="skel-base" style="height:14px;width:40%;margin-bottom:12px;"></div>' +
            '<div class="skel-base" style="height:36px;"></div>' +
          '</div>' +
        '</div>'
    ); }).join('');

    try {
        var res  = await fetch("/api/sneakers");
        if (!res.ok) throw new Error("API " + res.status);
        var data = await res.json();

        grid.innerHTML = "";
        data.forEach(function(shoe) {
            var card       = document.createElement("div");
            card.className = "product";
            card.innerHTML =
                '<button class="fav-btn" onclick="toggleHeart(this,\'' +
                    shoe.name.replace(/'/g,"\\'")+'\',\'' +
                    shoe.price + '\',\'' + shoe.image + '\')">' +
                    '<i class="fa fa-heart"></i>' +
                '</button>' +
                '<a href="/product/' + shoe.id + '" style="text-decoration:none;color:inherit;display:block;">' +
                    '<img src="' + shoe.image + '" class="shoe-img" alt="' + shoe.name + '">' +
                    '<div class="product-info-inner">' +
                        '<h3>' + shoe.name + '</h3>' +
                        '<p>' + shoe.price + '</p>' +
                    '</div>' +
                '</a>' +
                '<div style="padding:0 16px 16px;">' +
                    '<button class="product-cart-btn">Add to Cart</button>' +
                '</div>';
            card.querySelector(".product-cart-btn").addEventListener("click", function(e) {
                e.stopPropagation();
                addToCart(shoe.name, shoe.price, shoe.image);
            });
            grid.appendChild(card);
        });
    } catch (err) {
        console.error("Failed to load sneakers:", err);
        grid.innerHTML = "<p style='color:#e85d2f;padding:20px;font-family:Barlow,sans-serif;'>Failed to load sneakers. Please refresh.</p>";
    }
}

document.addEventListener("DOMContentLoaded", loadSneakers);