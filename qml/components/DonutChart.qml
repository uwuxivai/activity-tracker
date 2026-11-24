import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property var theme
    property var segments: []

    onSegmentsChanged: canvas.requestPaint()

    RowLayout {
        anchors.fill: parent
        spacing: 18

        Canvas {
            id: canvas
            Layout.preferredWidth: 180
            Layout.preferredHeight: 180
            Layout.alignment: Qt.AlignVCenter

            property color bgColor: root.theme.card
            onBgColorChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()

                var cx = width / 2
                var cy = height / 2
                var outerR = Math.min(cx, cy) - 6
                var innerR = outerR * 0.58

                var total = 0
                for (var i = 0; i < root.segments.length; i++) {
                    total += root.segments[i].seconds
                }

                if (total <= 0) {
                    ctx.beginPath()
                    ctx.arc(cx, cy, outerR, 0, Math.PI * 2)
                    ctx.fillStyle = root.theme.border
                    ctx.fill()
                } else {
                    var startAngle = -Math.PI / 2
                    for (var j = 0; j < root.segments.length; j++) {
                        var seg = root.segments[j]
                        var sweep = (seg.seconds / total) * Math.PI * 2
                        ctx.beginPath()
                        ctx.moveTo(cx, cy)
                        ctx.arc(cx, cy, outerR, startAngle, startAngle + sweep)
                        ctx.closePath()
                        ctx.fillStyle = seg.color
                        ctx.fill()
                        startAngle += sweep
                    }
                }

                ctx.beginPath()
                ctx.arc(cx, cy, innerR, 0, Math.PI * 2)
                ctx.fillStyle = root.theme.card
                ctx.fill()
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: root.segments

            delegate: RowLayout {
                required property var modelData
                width: ListView.view.width
                spacing: 8

                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: modelData.color
                }

                Label {
                    text: modelData.name
                    color: root.theme.text
                    font.pixelSize: 13
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Label {
                    text: modelData.durationText + " (" + modelData.share.toFixed(1) + "%)"
                    color: root.theme.muted
                    font.pixelSize: 12
                }
            }
        }
    }
}