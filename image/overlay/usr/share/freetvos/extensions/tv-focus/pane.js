/*
 * A highlight around the pane that has focus.
 *
 * Drawn inside the page rather than by the compositor. A KWin script cannot
 * draw a border or an overlay, and the alternative it can do, changing opacity,
 * dims the pane you are not watching, which is the opposite of what split view
 * is for. These are chromeless --app windows, so a border at the edge of the
 * document sits exactly on the edge of the window.
 *
 * Only shown while actually tiled. Working that out needs no message from the
 * compositor: a tiled pane is smaller than the screen, and a fullscreen one is
 * not. A border permanently around a fullscreen service would be noise.
 */
(function () {
    var ID = "__freetvos_pane_highlight__";
    var THICKNESS = 6;
    var SLACK = 8;   // window managers are a few pixels off; do not be brittle

    function isTiled() {
        if (!window.screen) return false;
        return (window.innerWidth < screen.width - SLACK) ||
               (window.innerHeight < screen.height - SLACK);
    }

    function frame() {
        var el = document.getElementById(ID);
        if (el) return el;
        el = document.createElement("div");
        el.id = ID;
        el.style.cssText = [
            "position:fixed",
            "inset:0",
            "border:" + THICKNESS + "px solid #3DDC97",
            "box-shadow:inset 0 0 22px rgba(61,220,151,0.35)",
            "pointer-events:none",
            "z-index:2147483647",
            "transition:opacity 120ms ease"
        ].join(";");
        return el;
    }

    function update() {
        var want = document.hasFocus() && isTiled();
        var el = document.getElementById(ID);
        if (want) {
            if (!el) {
                el = frame();
                // documentElement, not body: a page may replace body wholesale
                // during navigation and take the highlight with it.
                (document.documentElement || document.body).appendChild(el);
            }
            el.style.opacity = "1";
        } else if (el) {
            el.style.opacity = "0";
        }
    }

    window.addEventListener("focus", update, true);
    window.addEventListener("blur", update, true);
    window.addEventListener("resize", update);
    document.addEventListener("visibilitychange", update);
    document.addEventListener("DOMContentLoaded", update);
    // Focus can settle after load, and some sites reparent the document late.
    setInterval(update, 1000);
    update();
})();
