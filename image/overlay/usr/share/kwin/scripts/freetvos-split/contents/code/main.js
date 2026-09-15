/*
 * FreeTVOS split view.
 *
 * Installed and resident, not injected. KWin accepts a script handed to it over
 * DBus with loadScript, returns an id, starts without complaint, and never runs
 * it; a probe whose only job was to minimise a window proved that, silently. A
 * script packaged here and enabled in kwinrc is loaded by KWin itself at
 * startup, which is the supported path.
 *
 * Being resident also lets the script own its shortcuts, so nothing outside the
 * compositor has to ask it to do anything.
 */

function serviceWindows() {
    var all = workspace.windowList ? workspace.windowList() : workspace.clientList();
    var out = [];
    for (var i = 0; i < all.length; i++) {
        var w = all[i];
        if (!w || !w.normalWindow) continue;
        out.push(w);
    }
    /*
     * Every normal window, not just ones whose class matches. Filtering on
     * resourceClass starting with "freetvos-" matched nothing: Chromium's
     * --class sets WM_CLASS under X11, and under Wayland the app id comes from
     * elsewhere, so the filter silently excluded every window. A diagnostic
     * that minimised all normal windows worked while the same code filtered by
     * class did nothing, which is what isolated it.
     *
     * On a television this is also simply more correct. The shell is not a
     * normal window, so the only normal windows in the session are the
     * services themselves.
     *
     * Ordered by process id, which the audio half can see too. Sorting by
     * class would put the two halves in different orders whenever the class is
     * not what this side expects, which is exactly the trap above.
     */
    out.sort(function (a, b) { return (a.pid || 0) - (b.pid || 0); });
    return out;
}

function workArea() {
    return workspace.clientArea(KWin.MaximizeArea, workspace.activeScreen,
                                workspace.currentDesktop);
}

function tile(layout) {
    var wins = serviceWindows();
    if (wins.length === 0) return;
    if (pip.on) {
        if (pip.small) pip.small.keepAbove = false;
        pip = { on: false, main: null, small: null, corner: 0 };
    }

    // Fullscreen is a compositor mode, not a large geometry. A fullscreen
    // window ignores any rectangle set on it, so clearing it first is what
    // makes the difference between tiling and nothing happening.
    for (var i = 0; i < wins.length; i++) {
        if (wins[i].fullScreen) wins[i].fullScreen = false;
        if (wins[i].minimized) wins[i].minimized = false;
    }

    if (layout === 1) {
        wins[0].fullScreen = true;
        workspace.activeWindow = wins[0];
        clearDimming();
        return;
    }

    var area = workArea();
    var cols = 2;
    var rows = (layout === 4) ? 2 : 1;
    var count = Math.min(wins.length, cols * rows);
    var w = Math.floor(area.width / cols);
    var h = Math.floor(area.height / rows);

    for (var n = 0; n < count; n++) {
        wins[n].frameGeometry = {
            x: area.x + (n % cols) * w,
            y: area.y + Math.floor(n / cols) * h,
            width: w,
            height: h
        };
    }
    workspace.activeWindow = wins[0];
    clearDimming();
}

/*
 * Picture in picture.
 *
 * One service fills the screen and another sits small in a corner, above it.
 * The big one is maximised rather than made fullscreen: KWin draws the active
 * fullscreen window above everything kept above it, so a fullscreen main
 * picture would swallow the small one. Services have no window decoration, so
 * on a television maximised and fullscreen look the same.
 *
 * The small window starts top right. The bars along the bottom of the screen
 * sit in the overlay layer, above every window, and would cover a small
 * picture in either bottom corner.
 */
var CORNERS = ["top-right", "bottom-right", "bottom-left", "top-left"];
var pip = { on: false, main: null, small: null, corner: 0 };

function pipGeometry(area, corner) {
    var w = Math.round(area.width * 0.3);
    var h = Math.round(w * 9 / 16);
    var margin = Math.round(area.height * 0.04);
    var name = CORNERS[corner % CORNERS.length];
    var x = name.indexOf("right") >= 0 ? area.x + area.width - w - margin : area.x + margin;
    // Clear of a stack of bars when it has to sit at the bottom.
    var bottomClear = Math.round(area.height * 0.2);
    var y = name.indexOf("top") === 0 ? area.y + margin
                                      : area.y + area.height - h - bottomClear;
    return { x: x, y: y, width: w, height: h };
}

/*
 * Some pages put themselves back into fullscreen. YouTube's TV page does, a
 * moment after the layout takes it out, and a fullscreen window is drawn above
 * everything kept above it, so the small picture vanished behind the big one.
 * While picture in picture is on, fullscreen is taken straight back off the big
 * window whenever it comes back.
 */
function holdOutOfFullscreen(w) {
    if (!w || w.freetvosPipWatched) return;
    w.freetvosPipWatched = true;
    w.fullScreenChanged.connect(function () {
        if (pip.on && w === pip.main && w.fullScreen) {
            w.fullScreen = false;
            arrangePip();
        }
    });
}

function arrangePip() {
    var area = workArea();
    var main = pip.main, small = pip.small;
    if (!main || !small) return;
    holdOutOfFullscreen(main);
    holdOutOfFullscreen(small);
    [main, small].forEach(function (w) {
        if (w.fullScreen) w.fullScreen = false;
        if (w.minimized) w.minimized = false;
    });
    main.keepAbove = false;
    main.frameGeometry = { x: area.x, y: area.y, width: area.width, height: area.height };
    small.frameGeometry = pipGeometry(area, pip.corner);
    small.keepAbove = true;
    // The remote talks to the big picture; the small one is for watching.
    workspace.activeWindow = main;
    clearDimming();
}

/*
 * bigIndex picks the big picture by its place in process order, which the
 * shell can see too. Without it the focused window is the big one, which is
 * right for the remote's own shortcut and unknowable from outside the
 * compositor.
 */
function startPip(bigIndex) {
    var wins = serviceWindows();
    if (wins.length < 2) return;
    var main = null;
    if (bigIndex === 0 || bigIndex === 1) {
        main = wins[bigIndex];
    } else {
        var active = workspace.activeWindow;
        for (var i = 0; i < wins.length; i++) if (wins[i] === active) main = wins[i];
    }
    main = main || wins[0];
    var small = null;
    for (var j = 0; j < wins.length; j++) if (wins[j] !== main) { small = wins[j]; break; }
    // Anything else goes out of the way rather than sitting behind both.
    for (var k = 0; k < wins.length; k++) {
        if (wins[k] !== main && wins[k] !== small) wins[k].minimized = true;
    }
    pip = { on: true, main: main, small: small, corner: 0 };
    arrangePip();
}

function stopPip() {
    if (!pip.on) return;
    if (pip.small) { pip.small.keepAbove = false; pip.small.minimized = true; }
    if (pip.main) { pip.main.fullScreen = true; workspace.activeWindow = pip.main; }
    pip = { on: false, main: null, small: null, corner: 0 };
}

function togglePip() { if (pip.on) stopPip(); else startPip(); }

function swapPip() {
    if (!pip.on) return;
    var t = pip.main; pip.main = pip.small; pip.small = t;
    arrangePip();
}

function movePip() {
    if (!pip.on) return;
    pip.corner = (pip.corner + 1) % CORNERS.length;
    arrangePip();
}

// A window closing out from under the layout ends it cleanly, with whatever is
// left filling the screen, instead of leaving a small window stranded.
workspace.windowRemoved.connect(function (w) {
    if (!pip.on || (w !== pip.main && w !== pip.small)) return;
    var left = w === pip.main ? pip.small : pip.main;
    pip = { on: false, main: null, small: null, corner: 0 };
    if (left) { left.keepAbove = false; left.fullScreen = true; workspace.activeWindow = left; }
});

function focusNext() {
    var wins = serviceWindows();
    if (wins.length < 2) return;
    var current = 0;
    for (var i = 0; i < wins.length; i++) {
        if (wins[i] === workspace.activeWindow) { current = i; break; }
    }
    workspace.activeWindow = wins[(current + 1) % wins.length];
}

/*
 * Focus is shown by the page itself, not from here.
 *
 * The only thing a KWin script can change about a window's appearance is its
 * opacity, and dimming the pane you are not watching defeats the purpose of
 * showing two at once. The highlight is drawn by the bundled tv-focus
 * extension instead, which can put a coloured border exactly on the window
 * edge because these are chromeless app windows.
 *
 * Opacity is reset here so a pane left dimmed by an earlier version recovers.
 */
function clearDimming() {
    var wins = serviceWindows();
    for (var i = 0; i < wins.length; i++) wins[i].opacity = 1.0;
}

registerShortcut("FreeTVOS Single Pane", "FreeTVOS: single pane",
                 "Ctrl+Alt+1", function () { tile(1); });
registerShortcut("FreeTVOS Two Panes", "FreeTVOS: two panes",
                 "Ctrl+Alt+2", function () { tile(2); });
registerShortcut("FreeTVOS Four Panes", "FreeTVOS: four panes",
                 "Ctrl+Alt+4", function () { tile(4); });
registerShortcut("FreeTVOS Next Pane", "FreeTVOS: next pane",
                 "Ctrl+Alt+Tab", function () { focusNext(); });
registerShortcut("FreeTVOS Picture In Picture", "FreeTVOS: picture in picture",
                 "Ctrl+Alt+P", function () { togglePip(); });
registerShortcut("FreeTVOS PiP First Big", "FreeTVOS: picture in picture, first pane big",
                 "", function () { if (pip.on) stopPip(); startPip(0); });
registerShortcut("FreeTVOS PiP Second Big", "FreeTVOS: picture in picture, second pane big",
                 "", function () { if (pip.on) stopPip(); startPip(1); });
registerShortcut("FreeTVOS Swap Picture", "FreeTVOS: swap big and small picture",
                 "Ctrl+Alt+S", function () { swapPip(); });
registerShortcut("FreeTVOS Move Picture", "FreeTVOS: move the small picture",
                 "Ctrl+Alt+C", function () { movePip(); });

