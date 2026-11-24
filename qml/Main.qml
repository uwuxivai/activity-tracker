import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "views"

ApplicationWindow {
    id: root
    width: 1180
    height: 760
    minimumWidth: 940
    minimumHeight: 620
    visible: true
    title: "Activity Tracker"
    color: theme.bg

    property int currentTab: 0

    // Единая палитра тёмной и светлой тем
    property var theme: ({
        bg: settingsVM.darkTheme ? "#0f172a" : "#f1f5f9",
        sidebar: settingsVM.darkTheme ? "#111827" : "#ffffff",
        card: settingsVM.darkTheme ? "#1e293b" : "#ffffff",
        cardAlt: settingsVM.darkTheme ? "#162032" : "#f8fafc",
        border: settingsVM.darkTheme ? "#334155" : "#e2e8f0",
        text: settingsVM.darkTheme ? "#f8fafc" : "#0f172a",
        muted: settingsVM.darkTheme ? "#94a3b8" : "#64748b",
        accent: "#3b82f6",
        accentSoft: settingsVM.darkTheme ? "#1d4ed8" : "#dbeafe",
        success: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444"
    })

    // При нажатии «Закрыть» сворачиваем окно в системный трей, если не нажата кнопка «Выход»
    onClosing: (close) => {
        if (!settingsVM.quitting) {
            close.accepted = false
            root.hide()
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Боковая панель навигации
        Rectangle {
            Layout.preferredWidth: 230
            Layout.fillHeight: true
            color: theme.sidebar

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 8

                Label {
                    text: "Activity Tracker"
                    color: theme.text
                    font.pixelSize: 20
                    font.bold: true
                    Layout.bottomMargin: 4
                }

                Label {
                    text: dashboardVM.adapterName
                    color: theme.muted
                    font.pixelSize: 11
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    Layout.bottomMargin: 16
                }

                Repeater {
                    model: [
                        { title: "Дашборд", idx: 0 },
                        { title: "Таймлайн дня", idx: 1 },
                        { title: "Категории и правила", idx: 2 },
                        { title: "Настройки и экспорт", idx: 3 }
                    ]

                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        height: 42
                        radius: 8
                        color: root.currentTab === modelData.idx ? theme.accent : "transparent"

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: modelData.title
                            color: root.currentTab === modelData.idx ? "#ffffff" : theme.text
                            font.pixelSize: 14
                            font.weight: root.currentTab === modelData.idx ? Font.DemiBold : Font.Normal
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.currentTab = modelData.idx
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                // Индикатор текущего окна в реальном времени
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: liveCol.implicitHeight + 22
                    radius: 10
                    color: theme.cardAlt
                    border.color: theme.border
                    border.width: 1

                    ColumnLayout {
                        id: liveCol
                        anchors.fill: parent
                        anchors.margins: 11
                        spacing: 4

                        RowLayout {
                            spacing: 6
                            Rectangle {
                                width: 9
                                height: 9
                                radius: 5
                                color: settingsVM.isPaused
                                       ? theme.muted
                                       : (dashboardVM.liveIsAfk ? theme.warning : theme.success)
                            }
                            Label {
                                text: settingsVM.isPaused
                                      ? "Пауза"
                                      : (dashboardVM.liveIsAfk ? "Простой (AFK)" : "Идёт запись")
                                color: theme.text
                                font.pixelSize: 12
                                font.bold: true
                            }
                        }

                        Label {
                            text: dashboardVM.liveApp
                            color: theme.accent
                            font.pixelSize: 12
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Label {
                            text: dashboardVM.liveTitle
                            color: theme.muted
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Label {
                            text: "Категория: " + dashboardVM.liveCategory + " • Idle " + dashboardVM.liveIdle.toFixed(0) + "с"
                            color: theme.muted
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // Рабочая область экранов
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentTab

            DashboardView { theme: root.theme }
            TimelineView { theme: root.theme }
            RulesView { theme: root.theme }
            SettingsView { theme: root.theme }
        }
    }
}