import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root

    required property var theme
    property var hourlyData: []
    property int hoveredIndex: -1

    spacing: 6

    function activeSec(item) {
        if (!item) return 0
        if (item.activeSeconds !== undefined) return Number(item.activeSeconds)
        if (item.active_seconds !== undefined) return Number(item.active_seconds)
        return 0
    }

    function productiveSec(item) {
        if (!item) return 0
        if (item.productiveSeconds !== undefined) return Number(item.productiveSeconds)
        if (item.productive_seconds !== undefined) return Number(item.productive_seconds)
        return 0
    }

    function hourNumber(item, fallbackIndex) {
        if (item && item.hour !== undefined) return Number(item.hour)
        return fallbackIndex
    }

    function formatDuration(sec) {
        const total = Math.max(0, Math.round(sec))
        const h = Math.floor(total / 3600)
        const m = Math.floor((total % 3600) / 60)
        const s = total % 60
        if (h > 0) return h + " ч " + m + " мин"
        if (m > 0) return m + " мин " + s + " сек"
        return s + " сек"
    }

    function hoveredSummary() {
        if (hoveredIndex < 0 || !hourlyData || hoveredIndex >= hourlyData.length)
            return "Наведите на столбец"
        const item = hourlyData[hoveredIndex]
        const h = hourNumber(item, hoveredIndex)
        const h1 = h < 10 ? "0" + h : "" + h
        const next = (h + 1) % 24
        const h2 = next < 10 ? "0" + next : "" + next
        return h1 + ":00–" + h2 + ":00  •  Всего: " + formatDuration(activeSec(item))
            + "  •  Продуктивно: " + formatDuration(productiveSec(item))
    }

    readonly property real maxSeconds: {
        let m = 60
        if (!hourlyData) return m
        for (let i = 0; i < hourlyData.length; i++) {
            const v = activeSec(hourlyData[i])
            if (v > m) m = v
        }
        return m
    }

    Item {
        id: plotArea
        Layout.fillWidth: true
        Layout.fillHeight: true

        Row {
            id: barsRow
            anchors.fill: parent
            spacing: 0

            Repeater {
                id: barRepeater
                model: root.hourlyData

                Item {
                    id: slot
                    required property var modelData
                    required property int index

                    width: barRepeater.count > 0 ? barsRow.width / barRepeater.count : 0
                    height: barsRow.height

                    readonly property real totalVal: root.activeSec(modelData)
                    readonly property real prodVal: Math.min(totalVal, root.productiveSec(modelData))
                    readonly property real totalRatio: Math.min(1.0, totalVal / root.maxSeconds)
                    readonly property real prodRatio: Math.min(1.0, prodVal / root.maxSeconds)
                    readonly property bool isHovered: root.hoveredIndex === index

                    Rectangle {
                        anchors.fill: parent
                        radius: 4
                        color: slot.isHovered
                            ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, 0.14)
                            : "transparent"
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 2
                        anchors.rightMargin: 2
                        anchors.bottom: parent.bottom
                        height: slot.totalVal > 0 ? Math.max(4, (parent.height - 6) * slot.totalRatio) : 2
                        radius: 4
                        color: slot.totalVal > 0
                            ? (slot.isHovered ? Qt.lighter(root.theme.accent, 1.2) : root.theme.accent)
                            : root.theme.cardAlt

                        Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutQuad } }
                        Behavior on color  { ColorAnimation  { duration: 100 } }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: slot.prodVal > 0
                                ? Math.min(parent.height, Math.max(3, (slot.height - 6) * slot.prodRatio))
                                : 0
                            radius: 4
                            color: slot.isHovered ? Qt.lighter(root.theme.success, 1.15) : root.theme.success
                            visible: height > 0

                            Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutQuad } }
                        }
                    }
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true

            function updateHovered(mx) {
                const count = barRepeater.count
                if (count <= 0 || width <= 0) {
                    root.hoveredIndex = -1
                    return
                }
                const idx = Math.floor((mx / width) * count)
                root.hoveredIndex = Math.max(0, Math.min(count - 1, idx))
            }

            onEntered: updateHovered(mouseX)
            onPositionChanged: (mouse) => updateHovered(mouse.x)
            onExited: root.hoveredIndex = -1
        }
    }

    Row {
        Layout.fillWidth: true
        spacing: 0

        Repeater {
            model: root.hourlyData

            Label {
                required property var modelData
                required property int index

                readonly property int h: root.hourNumber(modelData, index)
                width: barRepeater.count > 0 ? parent.width / barRepeater.count : 0
                horizontalAlignment: Text.AlignHCenter
                text: h % 3 === 0 ? (h < 10 ? "0" + h : "" + h) : ""
                color: root.hoveredIndex === index ? root.theme.text : root.theme.muted
                font.pixelSize: 10
                font.bold: root.hoveredIndex === index
            }
        }
    }

    Label {
        Layout.fillWidth: true
        text: root.hoveredSummary()
        color: root.hoveredIndex >= 0 ? root.theme.text : root.theme.muted
        font.pixelSize: 12
        elide: Text.ElideRight
    }
}