import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import manager_ui

// One application card. Everything here mirrors AppCard in manager.py —
// same actions, same gates — routed through the bridge to the normal
// backend entry points.
Item {
    id: card

    required property var model
    readonly property bool showProblems: model.problems !== ""

    // Hover tint only — a dense list is hovered constantly, so movement
    // would be noise (Emil: tens/day interactions get no animation).
    readonly property bool hovered: mouse.hovered

    implicitHeight: cardRow.implicitHeight + 24
    Accessible.role: Accessible.ListItem
    Accessible.name: (model.pinned ? "Pinned. " : "") + model.name + ", "
                     + model.formatLabel + (model.version ? " " + model.version : "")
                     + ", " + model.statusLabel
                     + (showProblems ? ". Problems: " + model.problems : "")

    Rectangle {
        id: cardSurface
        anchors.fill: parent
        radius: 10
        color: card.hovered ? Theme.colors.hover : Theme.colors.surface
        border.color: card.activeFocus ? Theme.colors.focusRing : Theme.colors.border
        border.width: card.activeFocus ? 2 : 1

        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        cursorShape: Qt.ArrowHoverCursor
    }

    RowLayout {
        id: cardRow
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 12
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 14

        // Icon: real icon when recorded, letter avatar fallback for the
        // real lists case (missing icons are common — never a blank box).
        // Icon: real icon when it loads; letter avatar fallback when none is
        // recorded or the file fails — real lists have missing icons, and a
        // blank box is the one outcome never allowed.
        Rectangle {
            id: iconTile
            Layout.preferredWidth: 44
            Layout.preferredHeight: 44
            radius: 10
            readonly property bool haveImage: model.iconUrl !== "" && image.status === Image.Ready
            color: haveImage ? "transparent" : Theme.colors.iconFallbackBg
            Image {
                id: image
                anchors.fill: parent
                source: model.iconUrl
                sourceSize: Qt.size(44, 44)
                fillMode: Image.PreserveAspectFit
                mipmap: true
                visible: iconTile.haveImage
            }
            Label {
                anchors.fill: parent
                visible: !iconTile.haveImage
                text: model.initial
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.colors.textSecondary
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "★"
                    visible: model.pinned
                    font.pixelSize: 14
                    color: Theme.colors.accent
                    Layout.alignment: Qt.AlignVCenter
                }

                Label {
                    id: nameLabel
                    Layout.fillWidth: true
                    text: model.name
                    elide: Text.ElideRight
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    // Full name on hover; elide is the overflow answer for
                    // real lists with long names.
                    ToolTip.visible: nameLabel.truncated && card.hovered
                    ToolTip.delay: 400
                    ToolTip.text: model.name
                }

                // Status chip: dot + label, tone from the backend status.
                Rectangle {
                    id: statusChip
                    radius: 9
                    implicitHeight: 20
                    implicitWidth: chipRow.implicitWidth + 14
                    color: Theme.toneBg(model.statusTone)
                    border.color: Theme.tone(model.statusTone)
                    border.width: 0

                    Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 5
                        Rectangle {
                            width: 7; height: 7; radius: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: Theme.tone(model.statusTone)
                        }
                        Label {
                            text: model.statusLabel
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: Theme.tone(model.statusTone)
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Layout.alignment: Qt.AlignVCenter
                    Accessible.role: Accessible.StaticText
                    Accessible.name: model.statusLabel
                }
            }

            Label {
                Layout.fillWidth: true
                text: {
                    var parts = [model.formatLabel]
                    if (model.version && model.version !== 'unknown') parts.push(model.version)
                    if (model.container) parts.push(model.container)
                    parts.push(model.sizeText)
                    return parts.join(' · ')
                }
                elide: Text.ElideRight
                font.pixelSize: 13
                color: Theme.colors.textSecondary
                textFormat: Text.PlainText
            }

            Label {
                visible: card.showProblems
                Layout.fillWidth: true
                text: "⚠ " + model.problems
                elide: Text.ElideRight
                font.pixelSize: 12
                color: Theme.colors.danger
                textFormat: Text.PlainText
                ToolTip.visible: truncated && card.hovered
                ToolTip.delay: 400
                ToolTip.text: model.problems
            }
        }

        // Actions: always visible (never hover-hidden — keyboard users and
        // new users both need them without discovery cost).
        RowLayout {
            spacing: 8
            Layout.alignment: Qt.AlignVCenter

            Button {
                id: openButton
                enabled: model.canOpen
                text: qsTr("Open")
                font.pixelSize: 13
                font.weight: Font.Medium
                implicitWidth: Math.max(contentItem.implicitWidth + 24, 76)
                implicitHeight: 30

                background: Rectangle {
                    radius: 7
                    color: openButton.enabled
                           ? (openButton.pressed ? Qt.darker(Theme.colors.accent, 1.1) : Theme.colors.accent)
                           : Theme.colors.surfaceAlt
                    scale: openButton.pressed ? 0.97 : 1.0

                    Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: Theme.pressMs; easing.type: Easing.OutCubic } }
                }
                contentItem: Label {
                    text: openButton.text
                    font: openButton.font
                    color: openButton.enabled ? Theme.colors.accentText : Theme.colors.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: if (model.canOpen) bridge.openApp(model.key)
                Accessible.name: "Open " + model.name
            }

            Button {
                id: detailsButton
                text: qsTr("Details")
                font.pixelSize: 13
                implicitWidth: Math.max(contentItem.implicitWidth + 24, 76)
                implicitHeight: 30
                hoverEnabled: true

                background: Rectangle {
                    radius: 7
                    color: detailsButton.pressed ? Theme.colors.pressed
                         : detailsButton.hovered ? Theme.colors.hover
                         : "transparent"
                    border.color: Theme.colors.border
                    border.width: 1
                    scale: detailsButton.pressed ? 0.97 : 1.0

                    Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: Theme.pressMs; easing.type: Easing.OutCubic } }
                }
                contentItem: Label {
                    text: detailsButton.text
                    font: detailsButton.font
                    color: Theme.colors.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: bridge.showDetails(model.key)
                Accessible.name: "Details for " + model.name
            }

            Button {
                id: moreButton
                text: "⋮"
                font.pixelSize: 16
                implicitWidth: 30
                implicitHeight: 30
                hoverEnabled: true

                background: Rectangle {
                    radius: 7
                    color: moreButton.pressed ? Theme.colors.pressed
                         : moreButton.hovered ? Theme.colors.hover
                         : "transparent"
                    border.color: moreButton.visualFocus ? Theme.colors.focusRing : "transparent"
                    border.width: moreButton.visualFocus ? 2 : 0
                    scale: moreButton.pressed ? 0.97 : 1.0

                    Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: Theme.pressMs; easing.type: Easing.OutCubic } }
                }
                contentItem: Label {
                    text: moreButton.text
                    font: moreButton.font
                    color: Theme.colors.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                // Menus are high-frequency: they open instantly, no animation.
                onClicked: moreMenu.popup(moreButton, 0, moreButton.height + 4)
                Accessible.name: "More actions for " + model.name
            }

            Menu {
                id: moreMenu

                MenuItem {
                    text: qsTr("Reinstall")
                    onTriggered: bridge.reinstallApp(model.key)
                }
                MenuItem {
                    text: qsTr("Check for Updates")
                    visible: model.canUpdate
                    onTriggered: bridge.updateApp(model.key)
                }
                MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.colors.border } }
                MenuItem {
                    text: qsTr("Uninstall")
                    onTriggered: bridge.uninstallApp(model.key)
                }
                MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.colors.border } }
                MenuItem {
                    text: qsTr("View Logs")
                    onTriggered: bridge.showLogs(model.key)
                }
                MenuItem {
                    text: qsTr("Repair Launcher")
                    onTriggered: bridge.repairApp(model.key)
                }
                MenuItem {
                    text: qsTr("Open Diagnostics")
                    onTriggered: bridge.openDiagnostics(model.key)
                }
                MenuSeparator {
                    visible: model.isContainer
                    contentItem: Rectangle { implicitHeight: 1; color: Theme.colors.border }
                }
                MenuItem {
                    text: qsTr("Container Health…")
                    visible: model.isContainer
                    onTriggered: bridge.showHealth(model.key)
                }
                MenuItem {
                    text: qsTr("Repair Container")
                    visible: model.isContainer
                    onTriggered: bridge.repairContainer(model.key)
                }
                MenuItem {
                    text: qsTr("Re-export Launcher")
                    visible: model.isContainer
                    onTriggered: bridge.reexportLauncher(model.key)
                }
            }
        }
    }

    // Enter opens, Space toggles the action menu — the two most frequent
    // keyboard paths, both instant (no animation on keyboard actions).
    Keys.onReturnPressed: (event) => {
        if (model.canOpen) { bridge.openApp(model.key); event.accepted = true }
    }
    Keys.onEnterPressed: (event) => {
        if (model.canOpen) { bridge.openApp(model.key); event.accepted = true }
    }
    Keys.onMenuPressed: (event) => {
        moreMenu.popup(moreButton, 0, moreButton.height + 4)
        event.accepted = true
    }
}
