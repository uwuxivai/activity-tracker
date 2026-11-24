import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    required property var theme

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Категории и правила классификации"
                color: theme.text
                font.pixelSize: 22
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "Пересчитать всю историю"
                onClicked: rulesVM.recategorizeHistory()
            }
        }

        Label {
            visible: rulesVM.statusMessage.length > 0
            text: rulesVM.statusMessage
            color: theme.accent
            font.pixelSize: 13
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // Левая колонка: Категории
            Rectangle {
                Layout.preferredWidth: 360
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
                        text: "Категории"
                        color: theme.text
                        font.pixelSize: 16
                        font.bold: true
                    }

                    TextField {
                        id: catNameField
                        Layout.fillWidth: true
                        placeholderText: "Название категории..."
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        TextField {
                            id: catColorField
                            Layout.preferredWidth: 100
                            text: "#06b6d4"
                            placeholderText: "#HEX"
                        }

                        ComboBox {
                            id: catProdBox
                            Layout.fillWidth: true
                            textRole: "label"
                            valueRole: "val"
                            model: [
                                { label: "Продуктивно (+1)", val: 1 },
                                { label: "Нейтрально (0)", val: 0 },
                                { label: "Отвлекает (-1)", val: -1 }
                            ]
                        }

                        Button {
                            text: "+"
                            onClicked: {
                                rulesVM.addCategory(catNameField.text, catColorField.text, catProdBox.currentValue)
                                catNameField.clear()
                            }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 6
                        model: rulesVM.categories

                        delegate: Rectangle {
                            required property var modelData
                            width: ListView.view.width
                            height: 44
                            radius: 8
                            color: theme.cardAlt

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8

                                Rectangle {
                                    width: 12
                                    height: 12
                                    radius: 6
                                    color: modelData.color
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Label {
                                        text: modelData.name
                                        color: theme.text
                                        font.bold: true
                                        font.pixelSize: 13
                                    }
                                    Label {
                                        text: modelData.productivityLabel
                                        color: theme.muted
                                        font.pixelSize: 11
                                    }
                                }

                                Button {
                                    text: "✕"
                                    onClicked: rulesVM.deleteCategory(modelData.id)
                                }
                            }
                        }
                    }
                }
            }

            // Правая колонка: Правила
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
                        text: "Правила (проверяются по возрастанию приоритета)"
                        color: theme.text
                        font.pixelSize: 16
                        font.bold: true
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 3
                        columnSpacing: 8
                        rowSpacing: 8

                        TextField {
                            id: rulePatternField
                            Layout.fillWidth: true
                            Layout.columnSpan: 2
                            placeholderText: "Шаблон (напр. youtube или code|pycharm)"
                        }

                        ComboBox {
                            id: ruleFieldBox
                            Layout.fillWidth: true
                            textRole: "label"
                            valueRole: "val"
                            model: [
                                { label: "Заголовок окна", val: "window_title" },
                                { label: "Имя процесса", val: "app_name" }
                            ]
                        }

                        ComboBox {
                            id: ruleCatBox
                            Layout.fillWidth: true
                            textRole: "name"
                            valueRole: "id"
                            model: rulesVM.categories
                        }

                        RowLayout {
                            spacing: 8
                            CheckBox {
                                id: ruleRegexCheck
                                text: "Regex"
                            }
                            SpinBox {
                                id: rulePrioritySpin
                                from: 1
                                to: 999
                                value: 50
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Добавить правило"
                            onClicked: {
                                rulesVM.addRule(
                                    rulePatternField.text,
                                    ruleFieldBox.currentValue,
                                    ruleCatBox.currentValue || 0,
                                    ruleRegexCheck.checked,
                                    rulePrioritySpin.value
                                )
                                rulePatternField.clear()
                            }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 6
                        model: rulesVM.rules

                        delegate: Rectangle {
                            required property var modelData
                            width: ListView.view.width
                            height: 46
                            radius: 8
                            color: theme.cardAlt

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 10
                                spacing: 10

                                Label {
                                    text: "#" + modelData.priority
                                    color: theme.muted
                                    font.pixelSize: 12
                                    Layout.preferredWidth: 38
                                }

                                Label {
                                    text: modelData.pattern
                                    color: theme.text
                                    font.bold: true
                                    font.pixelSize: 13
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Label {
                                    text: modelData.matchFieldLabel + (modelData.isRegex ? " [Re]" : "")
                                    color: theme.muted
                                    font.pixelSize: 11
                                }

                                Label {
                                    text: modelData.categoryName
                                    color: modelData.categoryColor
                                    font.bold: true
                                    font.pixelSize: 12
                                }

                                Button {
                                    text: "✕"
                                    onClicked: rulesVM.deleteRule(modelData.id)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}