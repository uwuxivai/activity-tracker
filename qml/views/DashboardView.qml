import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: view
    required property var theme
    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: view.availableWidth - 48
        x: 24
        y: 22
        spacing: 18

        // Заголовок и переключатель периода
        RowLayout {
            Layout.fillWidth: true

            Label {
                text: "Аналитика активности"
                color: theme.text
                font.pixelSize: 22
                font.bold: true
            }

            Item { Layout.fillWidth: true }

            Repeater {
                model: [
                    { key: "today", label: "Сегодня" },
                    { key: "yesterday", label: "Вчера" },
                    { key: "week", label: "7 дней" },
                    { key: "month", label: "30 дней" }
                ]

                delegate: Button {
                    required property var modelData
                    text: modelData.label
                    onClicked: dashboardVM.setPeriod(modelData.key)

                    background: Rectangle {
                        radius: 8
                        color: dashboardVM.periodKey === modelData.key ? theme.accent : theme.card
                        border.color: theme.border
                        border.width: 1
                    }
                    contentItem: Label {
                        text: parent.text
                        color: dashboardVM.periodKey === modelData.key ? "#ffffff" : theme.text
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                        rightPadding: 12
                    }
                }
            }
        }

        // Карточки KPI
        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 14

            KpiCard {
                Layout.fillWidth: true
                theme: view.theme
                title: "Активное время"
                value: dashboardVM.activeTimeText
                subtitle: "Без учёта простоя"
                accentColor: theme.accent
            }

            KpiCard {
                Layout.fillWidth: true
                theme: view.theme
                title: "Индекс продуктивности"
                value: dashboardVM.productivityIndex.toFixed(1) + "%"
                subtitle: "Продуктивно: " + dashboardVM.productiveTimeText
                accentColor: theme.success
            }

            KpiCard {
                Layout.fillWidth: true
                theme: view.theme
                title: "Отвлечения"
                value: dashboardVM.distractingTimeText
                subtitle: "Категории с весом -1"
                accentColor: theme.danger
            }

            KpiCard {
                Layout.fillWidth: true
                theme: view.theme
                title: "Время простоя (AFK)"
                value: dashboardVM.afkTimeText
                subtitle: "Порог: " + settingsVM.afkThresholdMin + " мин"
                accentColor: theme.warning
            }
        }

        // Блок графиков (категории + почасовая активность)
        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 260
                radius: 12
                color: theme.card
                border.color: theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Label {
                        text: "Распределение по категориям"
                        color: theme.text
                        font.pixelSize: 15
                        font.bold: true
                    }

                    DonutChart {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        theme: view.theme
                        segments: dashboardVM.categoryChartData
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 260
                radius: 12
                color: theme.card
                border.color: theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Label {
                        text: "Почасовая активность (синий — всего, зелёный — продуктивно)"
                        color: theme.text
                        font.pixelSize: 15
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    HourlyBarChart {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        theme: view.theme
                        hourlyData: dashboardVM.hourlyChartData
                    }
                }
            }
        }

        // Топ приложений (связан с QAbstractListModel appsModel)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.max(220, appsList.count * 48 + 64)
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1
            Layout.bottomMargin: 24

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Label {
                    text: "Топ приложений за выбранный период"
                    color: theme.text
                    font.pixelSize: 15
                    font.bold: true
                }

                ListView {
                    id: appsList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    interactive: false
                    spacing: 8
                    model: appsModel

                    delegate: ColumnLayout {
                        width: appsList.width
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                width: 10
                                height: 10
                                radius: 5
                                color: model.categoryColor
                            }
                            Label {
                                text: model.appName
                                color: theme.text
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Label {
                                text: "• " + model.categoryName
                                color: theme.muted
                                font.pixelSize: 12
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: model.durationText + " (" + model.sharePercent.toFixed(1) + "%)"
                                color: theme.text
                                font.pixelSize: 12
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 6
                            radius: 3
                            color: theme.cardAlt

                            Rectangle {
                                width: parent.width * Math.min(1.0, model.sharePercent / 100.0)
                                height: parent.height
                                radius: 3
                                color: model.categoryColor
                            }
                        }
                    }
                }
            }
        }
    }
}