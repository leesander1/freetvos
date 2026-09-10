import QtQuick

/*
 * The third and last loading surface. Plymouth hands to SDDM which hands to
 * this, so a viewer would normally see three different screens on the way up.
 * Rather than trying to synchronise those handovers, which means teaching the
 * session to signal readiness back to the boot splash, all three draw the same
 * ground and the same mark. The handovers still happen; they just stop being
 * visible, which is the part that actually mattered.
 */
Image {
    id: root
    source: "images/background.png"
    fillMode: Image.PreserveAspectCrop
    property int stage

    Rectangle {
        anchors.fill: parent
        color: "#0B0E14"
    }

    Image {
        anchors.centerIn: parent
        source: "images/logo.png"
        height: root.height / 5
        fillMode: Image.PreserveAspectFit
        smooth: true
        // No fade. The mark is already on screen from the previous surface, so
        // animating it in would draw attention to a transition that is
        // otherwise unnoticeable.
    }
}
