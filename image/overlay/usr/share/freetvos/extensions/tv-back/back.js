/*
 * Backspace means Back, as on every television remote.
 *
 * A remote's Back button is handled by the compositor and closes the service.
 * A keyboard's Backspace reached the web page instead, and most services do
 * nothing with it, so it seemed not to work at all.
 *
 * Only when the page has not used the key itself, and nobody is typing: a
 * service with its own Back, like YouTube's television interface, keeps it,
 * and Backspace in a search box still deletes a letter. Otherwise it goes back
 * a page, and when there is no page to go back to it closes the service, which
 * returns to the home screen.
 *
 * The bubbling phase on the window, the last place a key arrives, so the page
 * has had every chance to claim it first.
 *
 * A service that claims Backspace but does nothing with it, as YouTube's
 * television interface does on its first screen, would otherwise trap the
 * viewer. Then a second Backspace within two seconds leaves, and a small note
 * says so: the "press Back again to exit" of every television.
 */
(function () {
  "use strict";
  if (window.top !== window) return;

  function typing() {
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

  function leave() {
    try {
      chrome.runtime.sendMessage({ op: "close" });
    } catch (e) {
      // The extension was reloaded underneath a page that is still open.
    }
  }

  var armedUntil = 0;
  var note = null;

  function showNote() {
    if (!note) {
      note = document.createElement("freetvos-back-note");
      note.setAttribute("popover", "manual");
      note.style.cssText = [
        // Above the ticker bars, which at their most take a fifth of the screen.
        "position:fixed", "inset:auto auto 22vh 50%", "transform:translateX(-50%)",
        "margin:0", "padding:14px 26px", "border:0", "border-radius:999px",
        "background:rgba(21,26,35,0.94)", "color:#E6EAF2",
        "font:500 22px/1.2 'Noto Sans',system-ui,sans-serif",
        "box-shadow:0 12px 40px rgba(0,0,0,0.5)", "color-scheme:dark"
      ].join(";");
      note.textContent = "Press Back again to leave";
    }
    (document.body || document.documentElement).appendChild(note);
    try { note.showPopover(); } catch (e) { /* already showing */ }
    setTimeout(function () {
      try { note.hidePopover(); } catch (e) { /* gone */ }
      note.remove();
    }, 2000);
  }

  function backspace(e) {
    return e.key === "Backspace" && !e.ctrlKey && !e.altKey && !e.metaKey &&
           !e.shiftKey && !typing();
  }

  // First to hear every key: registered before the service's own scripts
  // exist. A service that handles Backspace can stop it going any further,
  // as YouTube's television interface does, and a listener that only waited
  // for the key to arrive at the end of its journey never heard it at all.
  var pending = null;
  window.addEventListener("keydown", function (e) {
    if (!backspace(e)) return;
    if (Date.now() < armedUntil) {
      e.preventDefault();
      e.stopImmediatePropagation();
      leave();
      return;
    }
    var press = { address: location.href };
    pending = press;
    // Whether the service took it is known only afterwards. If it did, and it
    // went nowhere, the next press leaves.
    setTimeout(function () {
      if (pending === press && location.href === press.address) {
        armedUntil = Date.now() + 2000;
        showNote();
      }
      if (pending === press) pending = null;
    }, 300);
  }, true);

  // Last to hear it: the key reached here, so the service did nothing with it.
  window.addEventListener("keydown", function (e) {
    if (!backspace(e) || e.defaultPrevented || !pending) return;
    pending = null;
    e.preventDefault();
    var before = location.href;
    history.back();
    // Nothing to go back to leaves the address as it was. A real step back
    // either changes it, in a single-page service, or unloads this page, in
    // which case this never runs.
    setTimeout(function () {
      if (location.href === before) leave();
    }, 500);
  });
})();
