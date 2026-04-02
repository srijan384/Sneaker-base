// ============================================================
//  SNEAKER BASE — Client-Side Bot Detection v2
//  Collects signals → sends to /api/bot_signal
//  If server responds with redirect → browser goes to trap page
// ============================================================

(function () {
    // Don't run on the trap page itself (avoid redirect loop)
    if (window.location.pathname.startsWith("/exclusive-drops")) return;
    if (window.location.pathname.startsWith("/debug/")) return;
  
    const signals = {
      mouseMoved:      false,
      mousePoints:     0,
      scrolled:        false,
      keyPressed:      false,
      touchUsed:       false,
      clickCount:      0,
      timeOnPage:      0,
      webdriver:       false,
      headless:        false,
      pluginCount:     0,
      languageOk:      false,
      honeypotClicked: false,
      rapidRequests:   0,
      lastRequestTime: null,
      suspiciousUA:    false,
    };
  
    const pageStart = Date.now();
  
    // ── 1. Mouse movement ────────────────────────────────────────
    document.addEventListener("mousemove", () => {
      signals.mouseMoved = true;
      signals.mousePoints++;
    });
  
    // ── 2. Scroll ────────────────────────────────────────────────
    window.addEventListener("scroll", () => { signals.scrolled = true; });
  
    // ── 3. Keyboard ──────────────────────────────────────────────
    document.addEventListener("keydown", () => { signals.keyPressed = true; });
  
    // ── 4. Touch ─────────────────────────────────────────────────
    document.addEventListener("touchstart", () => { signals.touchUsed = true; });
  
    // ── 5. Click counter ─────────────────────────────────────────
    document.addEventListener("click", () => { signals.clickCount++; });
  
    // ── 6. Headless / WebDriver ──────────────────────────────────
    signals.webdriver =
      navigator.webdriver === true ||
      !!window.callPhantom || !!window._phantom || !!window.__nightmare;
  
    signals.headless =
      /HeadlessChrome/.test(navigator.userAgent) ||
      /PhantomJS/.test(navigator.userAgent) ||
      navigator.plugins.length === 0;
  
    signals.pluginCount = navigator.plugins.length;
  
    // ── 7. Language ──────────────────────────────────────────────
    signals.languageOk = navigator.language != null && navigator.language.length > 0;
  
    // ── 8. Suspicious User-Agent ─────────────────────────────────
    const ua = navigator.userAgent.toLowerCase();
    signals.suspiciousUA =
      /bot|crawl|spider|scrape|python|curl|wget|axios|java|go-http/.test(ua);
  
    // ── 9. Rapid fetch tracker ───────────────────────────────────
    const _origFetch = window.fetch;
    window.fetch = function (...args) {
      const now = Date.now();
      if (signals.lastRequestTime && now - signals.lastRequestTime < 300)
        signals.rapidRequests++;
      signals.lastRequestTime = now;
      return _origFetch.apply(this, args);
    };
  
    // ── 10. Honeypot injection ───────────────────────────────────
    function injectHoneypot() {
      // Hidden link
      const link = document.createElement("a");
      link.href = "/trap/exclusive-access";
      link.style.cssText =
        "position:absolute;left:-9999px;top:-9999px;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;";
      link.setAttribute("tabindex", "-1");
      link.setAttribute("aria-hidden", "true");
      link.textContent = "exclusive-access";
      link.addEventListener("click", (e) => {
        e.preventDefault();
        signals.honeypotClicked = true;
        sendSignals(true);
      });
      document.body.appendChild(link);
  
      // Hidden input field (catches form-filling bots)
      const inp = document.createElement("input");
      inp.type = "text"; inp.name = "bot_trap_field";
      inp.style.cssText =
        "position:absolute;left:-9999px;top:-9999px;width:0;height:0;opacity:0;";
      inp.setAttribute("tabindex", "-1");
      inp.setAttribute("aria-hidden", "true");
      inp.addEventListener("input", () => {
        signals.honeypotClicked = true;
        sendSignals(true);
      });
      document.body.appendChild(inp);
    }
  
    // ── 11. Score calculator ─────────────────────────────────────
    function calcBotScore() {
      let score = 0;
      if (!signals.mouseMoved)                         score += 25;
      if (signals.mousePoints < 3 && !signals.touchUsed) score += 15;
      if (!signals.scrolled)                           score += 10;
      if (!signals.keyPressed && signals.clickCount === 0) score += 10;
      if (signals.webdriver)                           score += 40;
      if (signals.headless)                            score += 30;
      if (signals.pluginCount === 0)                   score += 15;
      if (!signals.languageOk)                         score += 10;
      if (signals.suspiciousUA)                        score += 35;
      if (signals.rapidRequests > 3)                   score += 20;
      if (signals.honeypotClicked)                     score += 100;
      return Math.min(score, 100);
    }
  
    // ── 12. Send signals — handle redirect response ──────────────
    function sendSignals(immediate = false) {
      signals.timeOnPage = Math.round((Date.now() - pageStart) / 1000);
      const botScore = calcBotScore();
      const payload  = { ...signals, botScore, page: window.location.pathname, ts: Date.now() };
      const url      = "/api/bot_signal";
      const body     = JSON.stringify(payload);
  
      const handleResponse = (data) => {
        // If server says this is a bot AND gives a redirect URL → go there
        if (data && data.redirect && data.is_bot) {
          window.location.href = data.redirect;
        }
      };
  
      if (immediate) {
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          keepalive: true,
        })
          .then(r => r.json())
          .then(handleResponse)
          .catch(() => {});
      } else {
        // Non-blocking beacon for unload; use fetch for periodic checks
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
        })
          .then(r => r.json())
          .then(handleResponse)
          .catch(() => {});
      }
    }
  
    // ── 13. Schedule sends ───────────────────────────────────────
    // Send at 3s (early detection), 8s, and on unload
    setTimeout(() => sendSignals(true), 3000);
    setTimeout(() => sendSignals(true), 8000);
    window.addEventListener("beforeunload", () => {
      if (navigator.sendBeacon) {
        signals.timeOnPage = Math.round((Date.now() - pageStart) / 1000);
        const payload = { ...signals, botScore: calcBotScore(),
                          page: window.location.pathname, ts: Date.now() };
        navigator.sendBeacon("/api/bot_signal",
          new Blob([JSON.stringify(payload)], { type: "application/json" }));
      }
    });
  
    // ── 14. Init ─────────────────────────────────────────────────
    window.addEventListener("DOMContentLoaded", injectHoneypot);
  })();