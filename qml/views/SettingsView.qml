import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: view
    required property var theme
    property string pendingExportFormat: "csv"

    FileDialog {
        id: exportDialog
        title: "Сохранить отчёт активности"
        fileMode: FileDialog.SaveFile
        nameFilters: view.pendingExportFormat === "csv"
                     ? ["CSV файлы (*.csv)"]
                     : ["JSON файлы (*.json)"]
        onAccepted: {
            settingsVM.exportReport(
                selectedFile.toString(),
                view.pendingExportFormat,
                exportPeriodBox.currentValue
            )
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        Label {
            text: "Настройки и экспорт данных"
            color: theme.text
            font.pixelSize: 22
            font.bold: true
        }

        // Параметры трекинга
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: trackingGrid.implicitHeight + 36
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1

            GridLayout {
                id: trackingGrid
                anchors.fill: parent
                anchors.margins: 18
                columns: 2
                columnSpacing: 18
                rowSpacing: 12

                Label {
                    text: "Интервал опроса ОС (мс):"
                    color: theme.text
                }
                SpinBox {
                    id: pollSpin
                    from: 500
                    to: 5000
                    stepSize: 250
                    value: settingsVM.pollIntervalMs
                }

                Label {
                    text: "Порог простоя AFK (минут):"
                    color: theme.text
                }
                SpinBox {
                    id: afkSpin
                    from: 1
                    to: 30
                    value: Math.round(settingsVM.afkThresholdMin)
                }

                Label {
                    text: "Тёмная тема интерфейса:"
                    color: theme.text
                }
                Switch {
                    checked: settingsVM.darkTheme
                    onToggled: settingsVM.setDarkTheme(checked)
                }

                RowLayout {
                    Layout.columnSpan: 2
                    spacing: 12

                    Button {
                        text: "Сохранить параметры"
                        onClicked: settingsVM.saveTrackingSettings(pollSpin.value, afkSpin.value)
                    }

                    Button {
                        text: settingsVM.isPaused ? "Возобновить трекинг" : "Приостановить трекинг"
                        onClicked: settingsVM.togglePause()
                    }
                }
            }
        }

        // Экспорт отчётов
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: exportCol.implicitHeight + 36
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1

            ColumnLayout {
                id: exportCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Label {
                    text: "Экспорт отчёта"
                    color: theme.text
                    font.pixelSize: 16
                    font.bold: true
                }

                RowLayout {
                    spacing: 12

                    ComboBox {
                        id: exportPeriodBox
                        Layout.preferredWidth: 180
                        textRole: "label"
                        valueRole: "key"
                        model: [
                            { label: "За сегодня", key: "today" },
                            { label: "За вчера", key: "yesterday" },
                            { label: "За 7 дней", key: "week" },
                            { label: "За 30 дней", key: "month" }
                        ]
                    }

                    Button {
                        text: "Экспорт в CSV"
                        onClicked: {
                            view.pendingExportFormat = "csv"
                            exportDialog.open()
                        }
                    }

                    Button {
                        text: "Экспорт в JSON"
                        onClicked: {
                            view.pendingExportFormat = "json"
                            exportDialog.open()
                        }
                    }
                }

                Label {
                    visible: settingsVM.exportStatus.length > 0
                    text: settingsVM.exportStatus
                    color: theme.accent
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        // Диагностика платформы
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 84
            radius: 12
            color: theme.card
            border.color: theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 4

                Label {
                    text: "Диагностика платформенного бэкенда"
                    color: theme.text
                    font.bold: true
                }
                Label {
                    text: "Адаптер: " + dashboardVM.adapterName + "  •  БД: ~/.activity_tracker/activity.db (SQLite WAL)"
                    color: theme.muted
                    font.pixelSize: 12
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}