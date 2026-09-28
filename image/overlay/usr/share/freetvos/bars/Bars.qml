import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// The bars at the bottom of the screen.
//
// A layer-shell surface in the compositor's overlay layer, which is the layer
// above fullscreen windows, with no keyboard interactivity so the remote keeps
// talking to whatever is playing. Not an ordinary window, which also keeps it
// out of split view: the tiling script only arranges normal windows.
//
// It draws what the service hands it at /bars.json and nothing else. Which
// bars exist, what is on them and whether they should be showing at all are
// decided there, so this file has no schedule and no network code of its own.
Window {
    id: root

    property string feedUrl: Qt.application.arguments.length > 0
        ? Qt.application.arguments[Qt.application.arguments.length - 1] : ""
    // Every bar the service says is showing. What is drawn is `shown`: all of
    // them stacked, or one at a time when the layout is "rotate".
    property var bars: []
    property string size: "full"
    property string layout: "stacked"
    property int rotateEvery: 20
    property int turn: 0
    property var shown: layout === "rotate"
        ? (bars.length ? [bars[turn % bars.length]] : [])
        : bars
    // Thin is a little over half the height of full; every font below is a
    // fraction of this, so the whole bar scales with it.
    property int barHeight: Math.round(Screen.height * (size === "thin" ? 0.036 : 0.06))
    property string lastPayload: ""
    // One width for every label on the left, the widest of them. Sized each to
    // its own word, SCORES came out narrower than MARKETS above it, and a stack
    // of bars whose labels do not line up looks unfinished.
    property real badgeWidth: 0

    TextMetrics {
        id: titleMetrics
        font.pixelSize: root.barHeight * 0.36
        font.weight: Font.DemiBold
        font.family: "Noto Sans"
    }

    function measureBadges() {
        var widest = 0;
        for (var i = 0; i < bars.length; i++) {
            titleMetrics.text = bars[i].title || "";
            var w = bars[i].title ? titleMetrics.advanceWidth : 0;
            if (bars[i].logo)
                w += logoSlot + (bars[i].title ? barHeight * 0.18 : 0);
            widest = Math.max(widest, w);
        }
        badgeWidth = Math.ceil(widest + barHeight * 0.5);
    }

    // The room a logo gets, so a wide one cannot push one label past the rest.
    property real logoSlot: barHeight * 0.66 * 1.6

    // Measured across every bar, not only the one showing, so the label keeps
    // its width as the bars take turns rather than jumping with each one.
    onBarsChanged: measureBadges()
    onBarHeightChanged: measureBadges()

    width: Screen.width
    height: Math.max(1, shown.length * barHeight)
    color: "transparent"
    visible: bars.length > 0
    title: "FreeTVOS Bars"

    LayerShell.Window.scope: "freetvos-bars"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft
                               | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity:
        LayerShell.Window.KeyboardInteractivityNone

    function refresh() {
        var request = new XMLHttpRequest();
        request.onreadystatechange = function () {
            if (request.readyState !== XMLHttpRequest.DONE || request.status !== 200)
                return;
            // Only rebuild when something changed. Rebuilding every poll would
            // restart every crawl from the right-hand edge every few seconds.
            if (request.responseText === root.lastPayload)
                return;
            root.lastPayload = request.responseText;
            try {
                var payload = JSON.parse(request.responseText);
                root.size = payload.size || "full";
                root.layout = payload.layout || "stacked";
                root.rotateEvery = Math.max(5, payload.rotate_every || 20);
                root.bars = payload.bars || [];
            } catch (e) {
                root.bars = [];
            }
        };
        request.open("GET", root.feedUrl);
        request.send();
    }

    Timer {
        interval: 3000
        running: root.feedUrl !== ""
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    // Taking turns: the next bar every rotateEvery seconds. Nothing to rotate
    // with one bar, so the timer only runs with two or more.
    Timer {
        interval: root.rotateEvery * 1000
        running: root.layout === "rotate" && root.bars.length > 1
        repeat: true
        onTriggered: root.turn = (root.turn + 1) % Math.max(1, root.bars.length)
    }

    Column {
        anchors.fill: parent

        Repeater {
            model: root.shown

            delegate: Rectangle {
                id: strip
                required property var modelData
                width: root.width
                height: root.barHeight
                color: modelData.background || "#E60B0E14"
                clip: true

                // Each bar fades in as it arrives, so taking turns reads as a
                // change of channel rather than a flicker.
                opacity: 0
                NumberAnimation on opacity {
                    from: 0; to: 1; duration: 350; easing.type: Easing.OutQuad
                }

                Rectangle {
                    anchors.top: parent.top
                    width: parent.width
                    height: Math.max(2, Math.round(root.barHeight * 0.05))
                    color: strip.modelData.accent || "#3DDC97"
                }

                // A fixed label or logo on the left, like a news channel's
                // strap, with the crawl running underneath it.
                Rectangle {
                    id: badge
                    z: 2
                    height: parent.height
                    width: root.badgeWidth
                    color: strip.modelData.accent || "#3DDC97"

                    Row {
                        id: badgeRow
                        anchors.centerIn: parent
                        spacing: root.barHeight * 0.18

                        Image {
                            visible: (strip.modelData.logo || "") !== ""
                            source: strip.modelData.logo || ""
                            height: root.barHeight * 0.66
                            width: visible ? Math.min(root.logoSlot,
                                height * (implicitWidth / Math.max(1, implicitHeight))) : 0
                            fillMode: Image.PreserveAspectFit
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: strip.modelData.title || ""
                            visible: text !== ""
                            color: "#0B0E14"
                            font.pixelSize: root.barHeight * 0.36
                            font.weight: Font.DemiBold
                            font.family: "Noto Sans"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // The items, repeated end to end as many times as it takes to
                // cover the screen twice, sliding left by exactly one copy and
                // starting again. A short list crawled once leaves the bar
                // empty for most of each pass, which is what six stocks did
                // next to forty headlines.
                Item {
                    id: lane
                    x: badge.width
                    width: root.width - badge.width
                    height: parent.height
                    clip: true

                    Row {
                        id: measure
                        visible: false
                        spacing: root.barHeight * 0.9
                        Repeater {
                            model: strip.modelData.items || []
                            delegate: Row {
                                required property var modelData
                                spacing: root.barHeight * 0.18
                                Text { text: (modelData.star ? "\u2605 " : "") + (modelData.label || "");
                                       font.pixelSize: root.barHeight * 0.42; font.weight: Font.DemiBold;
                                       font.family: "Noto Sans" }
                                Text { text: modelData.value || ""; visible: text !== "";
                                       font.pixelSize: root.barHeight * 0.42; font.family: "Noto Sans" }
                                Text { text: (modelData.direction === "up" || modelData.direction === "down"
                                              ? "\u25B2 " : "") + (modelData.change || "");
                                       visible: text !== ""; font.pixelSize: root.barHeight * 0.36;
                                       font.family: "Noto Sans" }
                            }
                        }
                    }

                    // One copy's width, including the gap before the next copy.
                    property real copyWidth: measure.width + root.barHeight * 0.9
                    property int copies: copyWidth > 0
                        ? Math.max(2, Math.ceil(2 * width / copyWidth) + 1) : 0

                    Row {
                        id: crawl
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: root.barHeight * 0.9

                        Repeater {
                            model: lane.copies

                            delegate: Row {
                                spacing: root.barHeight * 0.9

                                Repeater {
                                    model: strip.modelData.items || []

                                    delegate: Row {
                                        required property var modelData
                                        spacing: root.barHeight * 0.18

                                        Text {
                                            id: labelText
                                            text: (modelData.star ? "\u2605 " : "") + (modelData.label || "")
                                            color: "#E6EAF2"
                                            font.pixelSize: root.barHeight * 0.42
                                            font.weight: Font.DemiBold
                                            font.family: "Noto Sans"
                                        }
                                        Text {
                                            text: modelData.value || ""
                                            visible: text !== ""
                                            color: "#E6EAF2"
                                            font.pixelSize: root.barHeight * 0.42
                                            font.family: "Noto Sans"
                                        }
                                        Text {
                                            text: modelData.direction === "up" ? "\u25B2 " + modelData.change
                                                : modelData.direction === "down" ? "\u25BC " + modelData.change
                                                : (modelData.change || "")
                                            visible: text !== ""
                                            color: modelData.direction === "up" ? "#3DDC97"
                                                 : modelData.direction === "down" ? "#FF6B6B"
                                                 : modelData.direction === "live" ? "#3DDC97"
                                                 : "#8C97AB"
                                            font.pixelSize: root.barHeight * 0.36
                                            font.family: "Noto Sans"
                                            anchors.baseline: labelText.baseline
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Constant speed rather than constant duration, so a long
                    // list crawls at the same pace as a short one.
                    NumberAnimation {
                        target: crawl
                        property: "x"
                        from: 0
                        to: -lane.copyWidth
                        duration: Math.max(2000, lane.copyWidth
                                           / Math.max(20, strip.modelData.speed || 140) * 1000)
                        loops: Animation.Infinite
                        running: lane.copyWidth > root.barHeight
                    }
                }
            }
        }
    }
}
