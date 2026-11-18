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
    readonly property bool canLaunch: model.canOpen && model.status === "installed"

    // Hover tint only — a dense list is hovered constantly, so movement
    // would be noise (Emil: tens/day interactions get no animation).
    readonly property bool hovered: mouse.containsMouse

    implicitHeight: cardRow.implicitHeight + 20
    Accessible.role: Accessible.ListItem
    Accessible.name: (model.pinned ? "Pinned. " : "") + model.name + ", "
                     + model.formatLabel + (model.version ? " " + model.version : "")
                     + ", " + model.statusLabel
                     + (showProblems ? ". Problems: " + model.problems : "")
    Accessible.description: (canLaunch ? qsTr("Enter: Open") : qsTr("Enter: Review"))
                            + qsTr("; Space: Details; Menu or Shift+F10: More actions")

    function activate() {
        if (canLaunch)
            bridge.openApp(model.key)
        else
            bridge.showDetails(model.key)
    }

    Rectangle {
        id: cardSurface
        anchors.fill: parent
        radius: 12
        color: card.hovered ? Theme.colors.surfaceAlt : Theme.colors.surface
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
        anchors.topMargin: 10
        anchors.bottomMargin: 10
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
            color: haveImage ? "transparent" : card.canLaunch
                   ? Theme.colors.iconFallbackBg : Theme.colors.warningBg
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
                color: card.canLaunch ? Theme.colors.accent : Theme.colors.warning
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    id: nameLabel
                    Layout.fillWidth: true
                    text: model.name
                    elide: Text.ElideRight
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    // Name uses the available space before the actions;
                    // genuinely long names elide, short names (Hayase,
                    // Stremio) show in full even at 720px.
                    ToolTip.visible: nameLabel.truncated && card.hovered
                    ToolTip.delay: 400
                    ToolTip.text: model.name
                }

                Label {
                    visible: model.pinned
                    text: "★"
                    color: Theme.colors.accent
                }
            }

            Label {
                Layout.fillWidth: true
                text: {
                    var parts = [model.formatLabel]
                    if (card.showProblems) return parts.concat(model.problems).join(' · ')
                    if (model.version && model.version !== 'unknown') parts.push(model.version)
                    if (model.container) parts.push(model.container)
                    if (model.sizeText !== "—") parts.push(model.sizeText)
                    return parts.join(' · ')
                }
                elide: Text.ElideRight
                font.pixelSize: 13
                color: Theme.colors.textSecondary
                textFormat: Text.PlainText
                ToolTip.visible: truncated && card.hovered
                ToolTip.delay: 400
                ToolTip.text: text
            }
        }

        // Actions: always visible (never hover-hidden — keyboard users and
        // new users both need them without discovery cost).
        RowLayout {
            spacing: 8
            Layout.alignment: Qt.AlignVCenter

            Item {
                Layout.preferredWidth: Math.max(136, statusText.implicitWidth + 18)
                implicitHeight: 26
                Rectangle {
                    anchors.right: parent.right
                    width: statusText.implicitWidth + 18
                    height: parent.height
                    radius: 13
                    readonly property string tone: card.canLaunch ? model.statusTone : "warning"
                    color: Theme.toneBg(tone)
                    Label {
                        id: statusText
                        anchors.centerIn: parent
                        text: card.canLaunch ? model.statusLabel : qsTr("Needs attention")
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: Theme.tone(parent.tone)
                    }
                }
            }

            Button {
                id: openButton
                text: card.canLaunch ? qsTr("Open") : qsTr("Review")
                // The card is the Tab stop (whole-item keyboard model);
                // buttons stay mouse/touch-only so Tab crosses the list.
                activeFocusOnTab: false
                font.pixelSize: 13
                font.weight: Font.Medium
                implicitWidth: Math.max(contentItem.implicitWidth + 24, 104)
                implicitHeight: 35

                background: Rectangle {
                    radius: 10
                    color: openButton.pressed ? Theme.colors.pressed
                         : openButton.hovered ? Theme.colors.hover : Theme.colors.surfaceAlt
                    scale: openButton.pressed ? 0.97 : 1.0

                    Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: Theme.pressMs; easing.type: Easing.OutCubic } }
                }
                contentItem: Label {
                    text: openButton.text
                    font: openButton.font
                    color: Theme.colors.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: card.activate()
                Accessible.name: qsTr("%1 — %2").arg(text).arg(model.name)
            }

            Button {
                id: moreButton
                text: "⋮"
                activeFocusOnTab: false
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
                ToolTip.visible: hovered
                ToolTip.delay: 400
                ToolTip.text: card.Accessible.description
            }

            Menu {
                id: moreMenu

                MenuItem {
                    text: qsTr("Details")
                    onTriggered: bridge.showDetails(model.key)
                }
                MenuItem {
                    text: model.pinned ? qsTr("Remove from Favorites")
                                       : qsTr("Add to Favorites")
                    checkable: true
                    checked: model.pinned
                    onTriggered: bridge.togglePin(model.key)
                }
                MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.colors.border } }

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

    // Enter uses the same launcher gate as the visible primary action.
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_F10 && event.modifiers === Qt.ShiftModifier) {
            moreMenu.popup(moreButton, 0, moreButton.height + 4)
            event.accepted = true
        }
    }
    Keys.onReturnPressed: (event) => {
        card.activate(); event.accepted = true
    }
    Keys.onEnterPressed: (event) => {
        card.activate(); event.accepted = true
    }
    Keys.onSpacePressed: (event) => {
        bridge.showDetails(model.key); event.accepted = true
    }
    Keys.onMenuPressed: (event) => {
        moreMenu.popup(moreButton, 0, moreButton.height + 4)
        event.accepted = true
    }
}
