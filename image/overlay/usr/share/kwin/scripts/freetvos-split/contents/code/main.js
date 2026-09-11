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

    // Fullscreen is a compositor mode, not a large geometry. A fullscreen
    // window ignores any rectangle set on it, so clearing it first is what
    // makes the difference between tiling and nothing happening.
    for (var i = 0; i < wins.length; i++) {
        if (wins[i].fullScreen) wins[i].fullScreen = false;
        if (wins[i].minimized) wins[i].minimized = false;
    }

    if (layout === 1) {
        splitActive = false;
        wins[0].fullScreen = true;
        workspace.activeWindow = wins[0];
        applyDimming();
        return;
    }
    splitActive = true;

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
    applyDimming();
}

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
 * Which pane has focus has to be visible from a sofa. A KWin script cannot
 * draw an overlay or a border, but it can set opacity, and a brightness
 * difference reads faster across a room than an outline does.
 *
 * Only applied while tiled. In single-pane mode there is nothing to compare
 * against and dimming would just look like a fault.
 */
var splitActive = false;
var DIM = 0.55;

function applyDimming() {
    var wins = serviceWindows();
    for (var i = 0; i < wins.length; i++) {
        if (!splitActive) {
            wins[i].opacity = 1.0;
        } else {
            wins[i].opacity = (wins[i] === workspace.activeWindow) ? 1.0 : DIM;
        }
    }
}

workspace.windowActivated.connect(function () { applyDimming(); });

registerShortcut("FreeTVOS Single Pane", "FreeTVOS: single pane",
                 "Ctrl+Alt+1", function () { tile(1); });
registerShortcut("FreeTVOS Two Panes", "FreeTVOS: two panes",
                 "Ctrl+Alt+2", function () { tile(2); });
registerShortcut("FreeTVOS Four Panes", "FreeTVOS: four panes",
                 "Ctrl+Alt+4", function () { tile(4); });
registerShortcut("FreeTVOS Next Pane", "FreeTVOS: next pane",
                 "Ctrl+Alt+Tab", function () { focusNext(); });

