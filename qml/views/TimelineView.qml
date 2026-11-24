import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    required property var theme
    property string hoveredSegmentInfo: "Наведите на цветной сегмент шкалы, чтобы посмотреть детали интервала"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // Шапка с навигацией по дням
        RowLayout {
            Layout.fillWidth: true

            Label {
                text: "Таймлайн дня"
                color: theme.text
                font.pixelSize: 22
                font.bold: true
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "◀"
                onClicked: dashboardVM.shiftTimelineDay(-1)
            }
            Label {
                text: dashboardVM.timelineDateLabel
                color: theme.text
                font.pixelSize: 14
                font.bold: true
                leftPadding: 10
                rightPadding: 10
            }
            Button {
                text: "▶"
                onClicked: dashboardVM.shiftTimelineDay(1)
            }
            Button {
                text: "Сегодня"
                onClicked: dashboardVM.resetTimelineToday()
            }
        }

        // Визуальная 24-часовая шкала активности
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 124
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8

                Label {
                    text: view.hoveredSegmentInfo
                    color: theme.muted
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Rectangle {
                    id: strip
                    Layout.fillWidth: true
                    height: 36
                    radius: 8
                    color: theme.cardAlt
                    clip: true

                    Repeater {
                        model: dashboardVM.timelineSegments

                        delegate: Rectangle {
                            required property var modelData
                            x: strip.width * modelData.startFraction
                            width: Math.max(2, strip.width * modelData.widthFraction)
                            height: strip.height
                            color: modelData.color
                            opacity: segArea.containsMouse ? 1.0 : 0.88

                            MouseArea {
                                id: segArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onEntered: {
                                    view.hoveredSegmentInfo = modelData.timeRange
                                        + "  •  " + modelData.appName
                                        + " (" + modelData.categoryName + ", " + modelData.durationText + ")"
                                        + " — " + modelData.windowTitle
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Repeater {
                        model: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]
                        delegate: Label {
                            required property string modelData
                            required property int index
                            text: modelData
                            color: theme.muted
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            horizontalAlignment: index === 6 ? Text.AlignRight : (index === 0 ? Text.AlignLeft : Text.AlignHCenter)
                        }
                    }
                }
            }
        }

        // Подробный журнал интервалов
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Label {
                    text: "Журнал интервалов (" + dashboardVM.timelineSessions.length + ")"
                    color: theme.text
                    font.pixelSize: 15
                    font.bold: true
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 6
                    model: dashboardVM.timelineSessions

                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 46
                        radius: 8
                        color: theme.cardAlt

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 12

                            Rectangle {
                                width: 10
                                height: 10
                                radius: 5
                                color: modelData.color
                            }

                            Label {
                                text: modelData.timeRange
                                color: theme.muted
                                font.pixelSize: 12
                                Layout.preferredWidth: 132
                            }

                            Label {
                                text: modelData.appName
                                color: theme.text
                                font.bold: true
                                font.pixelSize: 13
                                Layout.preferredWidth: 140
                                elide: Text.ElideRight
                            }

                            Label {
                                text: modelData.windowTitle
                                color: theme.muted
                                font.pixelSize: 12
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Label {
                                text: modelData.categoryName
                                color: modelData.color
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Label {
                                text: modelData.durationText
                                color: theme.text
                                font.pixelSize: 12
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }
            }
        }
    }
}