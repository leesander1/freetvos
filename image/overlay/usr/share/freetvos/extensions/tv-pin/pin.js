/*
 * Pin what is on screen to the home screen, from the remote.
 *
 * The favourites key on a remote, or P on a keyboard, opens a small panel over
 * the service with the show's name and poster, and Pin or Cancel. Until it is
 * open this listens for those keys and nothing else, so every other key still
 * belongs to the service. While it is open it takes every key, so nothing
 * pressed to choose a button also moves the service's own menus behind it.
 *
 * Not Menu, which was the first choice. Plasma Bigscreen binds Menu to its tasks
 * overview as a global shortcut, so the compositor takes it before any page sees
 * it, and that overview is not something to take away. Nothing else claims the
 * favourites key, which Linux reports as XF86Favorites and a page sees as
 * BrowserFavorites.
 *
 * The page supplies only a suggested name and poster. Which service this is,
 * and the address being pinned, are decided outside it: the address from the
 * browser's own record of the tab, and the service from the browser the helper
 * was started by. A page cannot pin itself into a different app.
 *
 * Its own selection rather than the page's focus. Services like YouTube's TV
 * interface take focus back the moment they see it leave, which on a real
 * button would leave nothing selected.
 */
(function () {
  "use strict";
  if (window.top !== window) return;

  var TAG = "freetvos-pin-panel";
  var AUTO_CLOSE_MS = 3500;

  var host = null;
  var parts = {};
  var buttons = [];
  var index = 0;
  var closeTimer = 0;
  var suggestion = { name: "", image: "" };

  // ------------------------------------------------------------ the page ---

  function editing() {
    var el = document.activeElement;
    while (el && el.shadowRoot && el.shadowRoot.activeElement) {
      el = el.shadowRoot.activeElement;
    }
    if (!el) return false;
    if (el.isContentEditable) return true;
    var tag = (el.tagName || "").toLowerCase();
    if (tag === "textarea" || tag === "select") return true;
    if (tag !== "input") return false;
    var type = (el.type || "text").toLowerCase();
    return ["button", "checkbox", "radio", "range", "submit", "reset",
            "image", "color", "file"].indexOf(type) < 0;
  }

  function meta(names) {
    for (var i = 0; i < names.length; i++) {
      var el = document.querySelector('meta[property="' + names[i] + '"]') ||
               document.querySelector('meta[name="' + names[i] + '"]');
      if (el && el.content) return el.content.trim();
    }
    return "";
  }

  // Single-page services change what is on screen without reloading, and their
  // preview tags go on describing whatever page they first loaded. Trust them
  // only when they say which page they describe, and it is this one.
  function tagsDescribeThisPage() {
    var described = meta(["og:url"]);
    if (!described) return false;
    try {
      var a = new URL(described, location.href);
      var b = new URL(location.href);
      return a.pathname.replace(/\/$/, "") === b.pathname.replace(/\/$/, "") &&
             (a.searchParams.get("v") || "") === (b.searchParams.get("v") || "");
    } catch (e) {
      return false;
    }
  }

  function cleanName(raw) {
    var s = (raw || "").replace(/[\u0000-\u001f\u007f]/g, " ")
                       .replace(/\s+/g, " ").trim();
    s = s.replace(/^\(\d+\)\s*/, "");          // YouTube's notification count
    s = s.replace(/^Watch\s+/i, "");
    s = s.split(/\s+\|\s+/)[0];                 // "Show | Service"
    // "Show - YouTube", but not "Show - Season 2 Episode 3": only a short last
    // part is taken to be the service's name.
    var dashed = s.split(/\s+[\u2013\u2014-]\s+/);
    if (dashed.length > 1 && dashed[dashed.length - 1].split(" ").length <= 2) {
      dashed.pop();
      s = dashed.join(" - ");
    }
    s = s.replace(/\s+Streaming Online$/i, "");
    return s.slice(0, 80).trim();
  }

  function suggest() {
    var current = tagsDescribeThisPage();
    var name = cleanName((current && meta(["og:title", "twitter:title"])) ||
                         document.title);
    var image = current ? meta(["og:image", "twitter:image"]) : "";
    if (!/^https:\/\//.test(image)) image = "";
    return { name: name, image: image };
  }

  // ------------------------------------------------------------- helper ---

  function ask(op, then) {
    var unavailable = { ok: false, error: "Pinning is not available right now." };
    try {
      chrome.runtime.sendMessage(
        { op: op, name: suggestion.name, image: suggestion.image },
        function (reply) {
          if (chrome.runtime.lastError || !reply) { then(unavailable); return; }
          then(reply);
        });
    } catch (e) {
      // The extension was reloaded underneath a page that is still open.
      then(unavailable);
    }
  }

  // -------------------------------------------------------------- panel ---

  var CSS = [
    ".panel{box-sizing:border-box;width:560px;max-width:calc(100vw - 96px);",
    "  background:#151A23;color:#E8ECF2;border:2px solid #2A3242;",
    "  border-radius:20px;padding:26px 28px;",
    "  font:20px/1.35 'Noto Sans',system-ui,sans-serif;",
    "  box-shadow:0 24px 70px rgba(0,0,0,.65)}",
    ".head{font-size:15px;letter-spacing:.08em;text-transform:uppercase;",
    "  color:#3DDC97;margin-bottom:16px}",
    ".show{display:flex;gap:18px;align-items:center}",
    ".poster{width:96px;height:136px;object-fit:cover;border-radius:10px;",
    "  background:#2A3242;flex:none}",
    ".name{font-size:26px;font-weight:600;overflow-wrap:anywhere}",
    ".msg{margin-top:16px;min-height:27px;color:#AAB4C3}",
    ".msg.bad{color:#FF8A8A}",
    ".buttons{display:flex;gap:14px;margin-top:18px}",
    ".button{flex:1;text-align:center;padding:14px 10px;border-radius:12px;",
    "  background:#1E2430;border:3px solid transparent}",
    ".button.sel{border-color:#3DDC97;box-shadow:0 0 22px rgba(61,220,151,.4)}",
    ".hint{margin-top:16px;font-size:15px;color:#6B7688}"
  ].join("\n");

  function build() {
    host = document.createElement(TAG);
    // A popover lives in the browser's top layer, above a service's own
    // fullscreen player, where anything merely given a high z-index is hidden.
    host.setAttribute("popover", "manual");
    host.style.cssText = [
      "position:fixed", "inset:48px 48px auto auto", "margin:0", "padding:0",
      "border:0", "background:transparent", "overflow:visible",
      "width:auto", "height:auto", "color-scheme:dark"
    ].join(";");
    var root = host.attachShadow({ mode: "closed" });
    var style = document.createElement("style");
    style.textContent = CSS;
    root.appendChild(style);

    var panel = document.createElement("div");
    panel.className = "panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Pin to the home screen");
    parts.head = el(panel, "div", "head", "Pin to the home screen");
    var show = el(panel, "div", "show");
    parts.poster = el(show, "img", "poster");
    parts.poster.alt = "";
    parts.poster.addEventListener("error", function () {
      parts.poster.hidden = true;
    });
    parts.name = el(show, "div", "name");
    parts.msg = el(panel, "div", "msg");
    parts.buttons = el(panel, "div", "buttons");
    // Not Back: on a remote that closes the whole service.
    el(panel, "div", "hint", "Left and right to choose, Enter to confirm, the same key again to close");
    root.appendChild(panel);
  }

  function el(parent, tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function say(text, bad) {
    parts.msg.textContent = text || "";
    parts.msg.className = bad ? "msg bad" : "msg";
  }

  function offer(list) {
    buttons = list;
    index = 0;
    parts.buttons.textContent = "";
    list.forEach(function (b) { b.node = el(parts.buttons, "div", "button", b.label); });
    draw();
  }

  function draw() {
    buttons.forEach(function (b, i) { b.node.classList.toggle("sel", i === index); });
  }

  function isOpen() {
    return !!(host && host.isConnected);
  }

  function open() {
    if (!host) build();
    clearTimeout(closeTimer);
    suggestion = suggest();
    parts.name.textContent = suggestion.name || "This page";
    parts.poster.hidden = !suggestion.image;
    if (suggestion.image) parts.poster.src = suggestion.image;
    (document.body || document.documentElement).appendChild(host);
    try { host.showPopover(); } catch (e) { /* already showing */ }

    say("Checking\u2026");
    offer([{ label: "Cancel", act: close }]);
    ask("status", function (r) {
      if (!isOpen()) return;
      if (!r.ok) {
        say(r.error, true);
        offer([{ label: "Close", act: close }]);
      } else if (r.pinned) {
        say("This is already on the home screen.");
        offer([{ label: "Remove pin", act: unpin }, { label: "Cancel", act: close }]);
      } else {
        say("");
        offer([{ label: "Pin", act: pin }, { label: "Cancel", act: close }]);
      }
    });
  }

  function close() {
    clearTimeout(closeTimer);
    if (!isOpen()) return;
    try { host.hidePopover(); } catch (e) { /* not showing */ }
    host.remove();
  }

  function finish(text) {
    say(text);
    offer([{ label: "Done", act: close }]);
    closeTimer = setTimeout(close, AUTO_CLOSE_MS);
  }

  function pin() {
    say("Pinning\u2026");
    offer([]);
    ask("pin", function (r) {
      if (!isOpen()) return;
      if (!r.ok) {
        say(r.error, true);
        offer([{ label: "Close", act: close }]);
        return;
      }
      finish("Pinned. It is on the home screen now.");
    });
  }

  function unpin() {
    say("Removing\u2026");
    offer([]);
    ask("unpin", function (r) {
      if (!isOpen()) return;
      if (!r.ok) {
        say(r.error, true);
        offer([{ label: "Close", act: close }]);
        return;
      }
      finish("Removed from the home screen.");
    });
  }

  // --------------------------------------------------------------- keys ---

  function opensPanel(e) {
    if (e.ctrlKey || e.altKey || e.metaKey) return false;
    if (e.key === "BrowserFavorites") return true;
    return (e.key === "p" || e.key === "P") && !e.shiftKey && !editing();
  }

  function swallow(e) {
    e.preventDefault();
    e.stopImmediatePropagation();
  }

  // Window, capture phase, registered before the page has run: the first
  // listener to see a key, ahead of anything the service adds later.
  window.addEventListener("keydown", function (e) {
    if (!isOpen()) {
      if (opensPanel(e)) { swallow(e); open(); }
      return;
    }
    swallow(e);
    if (e.repeat && e.key === "Enter") return;
    switch (e.key) {
      case "ArrowLeft":
      case "ArrowUp":
        index = Math.max(0, index - 1); draw(); break;
      case "ArrowRight":
      case "ArrowDown":
        index = Math.min(buttons.length - 1, index + 1); draw(); break;
      case "Enter":
      case " ":
        if (buttons[index]) buttons[index].act(); break;
      case "Escape":
      case "Backspace":
      case "BrowserBack":
      case "GoBack":
      case "BrowserFavorites":
      case "p":
      case "P":
        close(); break;
    }
  }, true);

  // The matching key-up, so a service that acts on release does not act on the
  // key that just chose a button.
  window.addEventListener("keyup", function (e) {
    if (isOpen() || e.key === "BrowserFavorites") swallow(e);
  }, true);
})();
