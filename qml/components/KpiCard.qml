import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: card
    required property var theme
    property string title: ""
    property string value: "—"
    property string subtitle: ""
    property color accentColor: "#3b82f6"

    radius: 12
    color: theme.card
    border.color: theme.border
    border.width: 1
    implicitHeight: 104

    Rectangle {
        width: 4
        height: parent.height - 28
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        radius: 2
        color: card.accentColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 16
        anchors.topMargin: 14
        anchors.bottomMargin: 14
        spacing: 4

        Label {
            text: card.title
            color: theme.muted
            font.pixelSize: 12
        }

        Label {
            text: card.value
            color: theme.text
            font.pixelSize: 24
            font.bold: true
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        Label {
            text: card.subtitle
            color: theme.muted
            font.pixelSize: 11
            visible: text.length > 0
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}