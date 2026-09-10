import QtQuick

// Deliberately not a login screen. Autologin is on, so drawing a form here
// would flash a prompt nobody is meant to answer. This is the same ground and
// the same mark as the frame before it, so the transition is not visible.
Rectangle {
    id: root
    color: "#0B0E14"
    anchors.fill: parent

    Image {
        anchors.centerIn: parent
        source: "/usr/share/plymouth/themes/freetvos/logo.png"
        height: root.height / 5
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
}
