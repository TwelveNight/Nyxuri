import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io

ShellRoot {
    PanelWindow {
        id: pin
        screen: Quickshell.screens.find(s => s.name === Quickshell.env("NYXURI_PIN_OUTPUT")) ?? Quickshell.screens[0]
        anchors { top: true; left: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "nyxuri-screenshot-pin"
        WlrLayershell.layer: WlrLayer.Overlay
        // A reference image must not steal keyboard focus from the working app.
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        color: "transparent"
        visible: image.status === Image.Ready
        property real zoom: 1
        readonly property real outputScale: Number(Quickshell.env("NYXURI_PIN_SCALE"))
        readonly property real nativeWidth: image.sourceSize.width / outputScale
        readonly property real nativeHeight: image.sourceSize.height / outputScale
        implicitWidth: Math.max(24, Math.ceil(nativeWidth * zoom) + 2)
        implicitHeight: Math.max(24, Math.ceil(nativeHeight * zoom) + 2)

        function place(x, y) {
            margins.left = Math.round(Math.max(0, Math.min(x, screen.width - implicitWidth)))
            margins.top = Math.round(Math.max(0, Math.min(y, screen.height - implicitHeight)))
        }

        Rectangle {
            anchors.fill: parent
            color: "#202020"
            border.width: 1
            border.color: mouse.containsMouse ? "#eeeeee" : "#777777"
            Image {
                id: image
                anchors.fill: parent
                anchors.margins: 1
                source: Quickshell.env("NYXURI_PIN_IMAGE")
                fillMode: Image.PreserveAspectFit
                cache: false
                onStatusChanged: {
                    if (status === Image.Error) {
                        console.error("Unable to decode screenshot PNG")
                        Qt.quit()
                    }
                    if (status === Image.Ready) {
                        // sourceSize-dependent bindings settle after the status signal.
                        Qt.callLater(() => {
                            pin.zoom = Math.min(1, (pin.screen.width - 64) / pin.nativeWidth, (pin.screen.height - 64) / pin.nativeHeight)
                            pin.place((pin.screen.width - pin.implicitWidth) / 2, (pin.screen.height - pin.implicitHeight) / 2)
                        })
                    }
                }
            }
            MouseArea {
                id: mouse
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                hoverEnabled: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                property point origin
                property real startLeft
                property real startTop
                onPressed: event => {
                    if (event.button === Qt.RightButton) {
                        console.info("Closing pin (right click)")
                        Qt.quit()
                        return
                    }
                    origin = mapToGlobal(event.x, event.y)
                    startLeft = pin.margins.left
                    startTop = pin.margins.top
                }
                onPositionChanged: event => {
                    if (!(pressedButtons & Qt.LeftButton)) return
                    const point = mapToGlobal(event.x, event.y)
                    pin.place(startLeft + point.x - origin.x, startTop + point.y - origin.y)
                }
                onWheel: event => {
                    const centerX = pin.margins.left + pin.width / 2
                    const centerY = pin.margins.top + pin.height / 2
                    const maximum = Math.min(4, (pin.screen.width - 16) / pin.nativeWidth, (pin.screen.height - 16) / pin.nativeHeight)
                    pin.zoom = Math.max(0.1, Math.min(maximum, pin.zoom * (event.angleDelta.y > 0 ? 1.1 : 1 / 1.1)))
                    pin.place(centerX - pin.implicitWidth / 2, centerY - pin.implicitHeight / 2)
                }
            }
        }
        IpcHandler {
            target: "pin"
            function close(): void {
                console.info("Closing pin (IPC)")
                Qt.quit()
            }
            function info(): string {
                return JSON.stringify({output: pin.screen.name, x: pin.margins.left, y: pin.margins.top,
                    width: pin.width, height: pin.height, zoom: pin.zoom, ready: image.status === Image.Ready})
            }
        }
    }
}
