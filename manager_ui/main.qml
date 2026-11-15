import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import manager_ui

ApplicationWindow {
    id: window
    width: 940
    height: 680
    minimumWidth: 720
    minimumHeight: 520
    visible: true
    title: qsTr("AppInstall — My Applications")
    color: Theme.colors.window

    // Screenshot contract for --screenshot: the QML engine returns the
    // base QWindow wrapper for this root, which lacks grabWindow(); QML
    // functions stay invokable through the dynamic metaobject, so the
    // grab itself lives here. grabToImage needs an item with a QML
    // engine — grabRoot, not the engine-less window contentItem.
    function saveWindowShot(path) {
        grabRoot.grabToImage(function(result) {
            result.saveToFile(path)
            Qt.quit()
        })
    }

    Component.onCompleted: {
        Theme.reducedMotion = bridge.reducedMotion
        Theme.mode = bridge.dark ? "dark" : "light"
        searchField.forceActiveFocus()
    }

    Connections {
        target: bridge
        function onDarkChanged() { Theme.mode = bridge.dark ? "dark" : "light" }
    }

    // Auto update checks live in the bridge (QTimer + APPINSTALL
    // _DISABLE_UPDATE_TIMER + helper gates); the QML layer never spawns
    // network work on its own.

    // Close guard: a running batch pipeline is cancelled first, an
    // AppInstall upgrade blocks closing, a running check is killed.
    onClosing: (close) => {
        if (!bridge.allowClose()) {
            close.accepted = false
        }
    }

    // ── drag and drop: same acceptance rules and batch dialog as the
    //    widgets window (PACKAGE_MIMES classification in manager.py) ─────
    DropArea {
        anchors.fill: parent
        onEntered: (drag) => dropShade.visible = bridge.dropAcceptable(drag.urls)
        onExited: dropShade.visible = false
        onDropped: (drop) => {
            dropShade.visible = false
            if (drop.hasUrls) bridge.dropPackages(drop.urls)
        }
    }

    Rectangle {
        id: dropShade
        anchors.fill: parent
        anchors.margins: 6
        radius: 12
        color: Theme.colors.successBg
        border.color: Theme.colors.success
        border.width: 2
        visible: false
        z: 10

        Label {
            id: dropHint
            anchors.centerIn: parent
            text: qsTr("Drop package files to install")
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: Theme.colors.success
            topPadding: 10
            bottomPadding: 10
            leftPadding: 16
            rightPadding: 16
            background: Rectangle {
                radius: 8
                color: Theme.colors.surface
            }
        }
    }

    // Grab root for --screenshot: a QML-declared item that paints the
    // window background and contains all content. grabToImage only works
    // on items with a QML engine, and the window's own contentItem (the
    // previous target) is engine-less. Stacking is unchanged: the shade
    // keeps z: 10 above this, the inner background keeps z: -1 below the
    // layout.
    Rectangle {
        id: grabRoot
        anchors.fill: parent
        color: Theme.colors.window

    // Opaque window background: grabs and repaints must never show the
    // platform clear color through unlit regions. Behind the layout, not a
    // layout child.
    Rectangle {
        anchors.fill: parent
        color: Theme.colors.window
        z: -1
        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── header ───────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: headerRow.implicitHeight + 24
            color: Theme.colors.surface

            Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 16
                spacing: 12

                Label {
                    text: qsTr("My Applications")
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }

                // Theme pill: shows the active mode, opens the same three
                // choices the widgets window offers (system follow included).
                Button {
                    id: themeButton
                    text: bridge.themeChoice === 'auto' ? qsTr("System")
                          : bridge.themeChoice === 'dark' ? qsTr("Dark")
                          : qsTr("Light")
                    font.pixelSize: 13
                    implicitHeight: 32
                    implicitWidth: themeLabel.implicitWidth + 24
                    hoverEnabled: true

                    background: Rectangle {
                        radius: 8
                        color: themeButton.pressed ? Theme.colors.pressed
                             : themeButton.hovered ? Theme.colors.hover
                             : "transparent"
                        border.color: themeButton.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: themeButton.visualFocus ? 2 : 1

                        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Label {
                        id: themeLabel
                        text: themeButton.text
                        font: themeButton.font
                        color: Theme.colors.text
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: themeMenu.popup(themeButton, 0, themeButton.height + 4)
                    Accessible.name: qsTr("Theme: %1").arg(themeButton.text)

                    Menu {
                        id: themeMenu

                        MenuItem {
                            text: qsTr("Follow system")
                            checkable: true
                            checked: bridge.themeChoice === 'auto'
                            onTriggered: bridge.setTheme('auto')
                        }
                        MenuItem {
                            text: qsTr("Light")
                            checkable: true
                            checked: bridge.themeChoice === 'light'
                            onTriggered: bridge.setTheme('light')
                        }
                        MenuItem {
                            text: qsTr("Dark")
                            checkable: true
                            checked: bridge.themeChoice === 'dark'
                            onTriggered: bridge.setTheme('dark')
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Install entry points: the widgets window's exact flows,
                // reached through the bridge's normal-entry-point rule.
                Button {
                    id: installFileButton
                    text: qsTr("Install from File…")
                    font.pixelSize: 13
                    implicitHeight: 32
                    implicitWidth: installFileLabel.implicitWidth + 24
                    hoverEnabled: true

                    background: Rectangle {
                        radius: 8
                        color: installFileButton.pressed ? Theme.colors.pressed
                             : installFileButton.hovered ? Theme.colors.hover
                             : "transparent"
                        border.color: installFileButton.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: installFileButton.visualFocus ? 2 : 1

                        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Label {
                        id: installFileLabel
                        text: installFileButton.text
                        font: installFileButton.font
                        color: Theme.colors.text
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: bridge.installFromFile()
                    Accessible.name: qsTr("Install a package from a file")
                }

                Button {
                    id: installUrlButton
                    text: qsTr("Install from URL…")
                    font.pixelSize: 13
                    implicitHeight: 32
                    implicitWidth: installUrlLabel.implicitWidth + 24
                    hoverEnabled: true

                    background: Rectangle {
                        radius: 8
                        color: installUrlButton.pressed ? Theme.colors.pressed
                             : installUrlButton.hovered ? Theme.colors.hover
                             : "transparent"
                        border.color: installUrlButton.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: installUrlButton.visualFocus ? 2 : 1

                        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Label {
                        id: installUrlLabel
                        text: installUrlButton.text
                        font: installUrlButton.font
                        color: Theme.colors.text
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: bridge.installFromUrl()
                    Accessible.name: qsTr("Install a package from a URL")
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.colors.border }

        // ── toolbar: search first, then state filters ─────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 16
            Layout.topMargin: 14
            Layout.bottomMargin: 8
            spacing: 10

            // Search: the primary control, prominent and always visible.
            TextField {
                id: searchField
                Layout.fillWidth: true
                Layout.maximumWidth: 420
                placeholderText: qsTr("Search applications…")
                font.pixelSize: 14
                color: Theme.colors.text
                placeholderTextColor: Theme.colors.textSecondary
                selectByMouse: true
                onTextChanged: appsModel.setSearch(text)
                Keys.onEscapePressed: (event) => {
                    if (text !== "") { text = ""; event.accepted = true }
                }

                background: Rectangle {
                    radius: 8
                    color: Theme.colors.surface
                    border.color: searchField.activeFocus ? Theme.colors.focusRing : Theme.colors.border
                    border.width: searchField.activeFocus ? 2 : 1

                    Behavior on border.color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                }
                verticalAlignment: TextInput.AlignVCenter
                leftPadding: 12
                rightPadding: 12
                topPadding: 7
                bottomPadding: 7
            }

            // Status filter.
            ComboBox {
                id: statusFilter
                implicitHeight: 32
                font.pixelSize: 13
                model: ListModel {
                    ListElement { label: qsTr("All statuses"); value: "all" }
                    ListElement { label: qsTr("Installed"); value: "installed" }
                    ListElement { label: qsTr("Needs repair"); value: "needs-repair" }
                    ListElement { label: qsTr("Files missing"); value: "missing" }
                    ListElement { label: qsTr("Stale record"); value: "stale" }
                    ListElement { label: qsTr("Corrupted"); value: "corrupted" }
                }
                textRole: "label"
                valueRole: "value"
                currentIndex: 0
                onActivated: (index) => appsModel.setStatusFilter(currentValue)
                Component.onCompleted: appsModel.setStatusFilter(currentValue)

                background: Rectangle {
                    radius: 7
                    color: Theme.colors.surface
                    border.color: statusFilter.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                    border.width: statusFilter.visualFocus ? 2 : 1
                }
                contentItem: Label {
                    text: statusFilter.displayText
                    font: statusFilter.font
                    color: Theme.colors.text
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 10
                    rightPadding: statusFilter.indicator.width + 6
                }
                indicator: Label {
                    text: "▾"
                    color: Theme.colors.textSecondary
                    font.pixelSize: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                }
                delegate: ItemDelegate {
                    id: statusDelegate
                    required property var model
                    width: statusFilter.width
                    contentItem: Label {
                        text: statusDelegate.model.label
                        font.pixelSize: 13
                        color: Theme.colors.text
                        verticalAlignment: Text.AlignVCenter
                    }
                    highlighted: statusFilter.highlightedIndex === index
                    background: Rectangle {
                        radius: 5
                        color: statusDelegate.highlighted ? Theme.colors.hover : "transparent"
                    }
                }
                popup: Popup {
                    y: statusFilter.height + 4
                    width: statusFilter.width
                    padding: 4
                    background: Rectangle {
                        radius: 8
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                    }
                }
                Accessible.name: qsTr("Status filter")
            }

            // Sort.
            ComboBox {
                id: sortCombo
                implicitHeight: 32
                font.pixelSize: 13
                model: ListModel {
                    ListElement { label: qsTr("Name (A–Z)"); value: "name-asc" }
                    ListElement { label: qsTr("Name (Z–A)"); value: "name-desc" }
                    ListElement { label: qsTr("Recently launched"); value: "recent" }
                    ListElement { label: qsTr("Size (largest)"); value: "size" }
                }
                textRole: "label"
                valueRole: "value"
                currentIndex: 0
                onActivated: (index) => appsModel.setSort(currentValue)
                Component.onCompleted: appsModel.setSort(currentValue)

                background: Rectangle {
                    radius: 7
                    color: Theme.colors.surface
                    border.color: sortCombo.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                    border.width: sortCombo.visualFocus ? 2 : 1
                }
                contentItem: Label {
                    text: sortCombo.displayText
                    font: sortCombo.font
                    color: Theme.colors.text
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 10
                    rightPadding: sortCombo.indicator.width + 6
                }
                indicator: Label {
                    text: "▾"
                    color: Theme.colors.textSecondary
                    font.pixelSize: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                }
                delegate: ItemDelegate {
                    id: sortDelegate
                    required property var model
                    width: sortCombo.width
                    contentItem: Label {
                        text: sortDelegate.model.label
                        font.pixelSize: 13
                        color: Theme.colors.text
                        verticalAlignment: Text.AlignVCenter
                    }
                    highlighted: sortCombo.highlightedIndex === index
                    background: Rectangle {
                        radius: 5
                        color: sortDelegate.highlighted ? Theme.colors.hover : "transparent"
                    }
                }
                popup: Popup {
                    y: sortCombo.height + 4
                    width: sortCombo.width
                    padding: 4
                    background: Rectangle {
                        radius: 8
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                    }
                }
                Accessible.name: qsTr("Sort order")
            }
        }

        // ── format chips + count ─────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            Layout.bottomMargin: 10
            spacing: 10

            // Flow (not a row): the chips wrap onto a second line at narrow
            // widths instead of squeezing the count label out of the window.
            Flow {
                Layout.fillWidth: true
                spacing: 6

                ButtonGroup { id: formatGroup }

                Repeater {
                    model: [
                        { label: qsTr("All"),      value: "all" },
                        { label: qsTr("AppImage"), value: "appimage" },
                        { label: qsTr("Flatpak"),  value: "flatpak" },
                        { label: qsTr("DEB"),      value: "deb" },
                        { label: qsTr("RPM"),      value: "rpm" },
                    ]

                    delegate: CheckButton {
                        ButtonGroup.group: formatGroup
                        checkText: modelData.label
                        onClicked: appsModel.setFormatFilter(modelData.value)
                        Component.onCompleted: if (index === 0) checked = true
                    }
                }
            }

            Label {
                id: countLabel
                text: appsModel.count === 1
                      ? qsTr("1 application")
                      : qsTr("%1 applications").arg(appsModel.count)
                font.pixelSize: 13
                color: Theme.colors.textSecondary
                textFormat: Text.PlainText
            }
        }

        // ── update banner ────────────────────────────────────────────
        Rectangle {
            id: updateBanner
            // Visible whenever there is something to act on: an available
            // tag, a running check/install, or the last status line.
            visible: bridge.updateTag !== "" || bridge.updateStatus !== ""
            Layout.fillWidth: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            Layout.bottomMargin: 10
            implicitHeight: 44
            radius: 9
            color: Theme.colors.surface
            border.color: bridge.updateTag !== "" ? Theme.colors.accent : Theme.colors.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 10
                spacing: 10

                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: bridge.updateTag !== "" ? Theme.colors.accent : Theme.colors.textSecondary
                    Layout.alignment: Qt.AlignVCenter
                }
                Label {
                    text: bridge.updateStatus
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: Theme.colors.text
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    textFormat: Text.PlainText
                }
                Button {
                    id: updateCheckButton
                    text: qsTr("Check for Updates")
                    visible: bridge.updateTag === "" && bridge.actionVisible
                    font.pixelSize: 13
                    implicitHeight: 30
                    implicitWidth: Math.max(contentItem.implicitWidth + 20, 110)

                    background: Rectangle {
                        radius: 7
                        color: "transparent"
                        border.color: updateCheckButton.enabled ? Theme.colors.border : "transparent"
                        border.width: 1
                        Behavior on border.color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Label {
                        text: updateCheckButton.text
                        font.pixelSize: 13
                        color: Theme.colors.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: bridge.checkUpdates(true)
                }
                Button {
                    id: updateBannerButton
                    text: qsTr("Update AppInstall")
                    visible: bridge.updateTag !== ""
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    implicitHeight: 30
                    implicitWidth: Math.max(contentItem.implicitWidth + 24, 140)

                    background: Rectangle {
                        radius: 7
                        color: updateBannerButton.pressed ? Qt.darker(Theme.colors.accent, 1.1) : Theme.colors.accent
                        scale: updateBannerButton.pressed ? 0.97 : 1.0

                        Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
                        Behavior on scale { NumberAnimation { duration: Theme.pressMs; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Label {
                        text: updateBannerButton.text
                        font: updateBannerButton.font
                        color: Theme.colors.accentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: bridge.installUpdate()
                }
            }
        }

        // ── list ─────────────────────────────────────────────────────
        Item {
            id: contentArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16

            ListView {
                id: appList
                anchors.fill: parent
                model: appsModel
                clip: true
                spacing: 8
                currentIndex: 0
                keyNavigationEnabled: true
                // The delegate (card) is the Tab stop: with the ListView
                // itself grabbable, Tab stopped here and never descended
                // into the cards, leaving every card action keyboard-
                // unreachable. Cards move with Up/Down (see the delegate).
                activeFocusOnTab: false

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }

                // No entrance transition: the model resets on every search
                // keystroke and filter change, so a delegate entrance would
                // re-run on high-frequency operations. Cards appear in place;
                // feedback lives in hover/press color and the status line.

                delegate: AppCard {
                    required property int index
                    width: appList.width
                    activeFocusOnTab: true
                    onActiveFocusChanged: {
                        if (activeFocus) {
                            appList.currentIndex = index
                            appList.positionViewAtIndex(index, ListView.Contain)
                        }
                    }
                    Keys.onUpPressed: (event) => appList.moveCardFocus(-1, event)
                    Keys.onDownPressed: (event) => appList.moveCardFocus(1, event)
                }

                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Home) {
                        appList.focusCard(0); event.accepted = true
                    } else if (event.key === Qt.Key_End) {
                        appList.focusCard(appsModel.rowCount() - 1); event.accepted = true
                    }
                }

                function focusCard(index) {
                    if (index < 0 || index >= appsModel.rowCount()) return
                    currentIndex = index
                    positionViewAtIndex(index, ListView.Contain)
                    // Realize delegates before focusing an offscreen target.
                    forceLayout()
                    var item = currentItem
                    if (item) item.forceActiveFocus()
                }

                function moveCardFocus(delta, event) {
                    event.accepted = true
                    focusCard(currentIndex + delta)
                }
            }

            // Empty state: type-led, centered over the list area.
            ColumnLayout {
                visible: appsModel.count === 0 && !bridge.loading
                anchors.centerIn: parent
                spacing: 6

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("No AppInstall-managed applications found")
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                }
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("Install a file to begin — drop a package anywhere in this window.")
                    font.pixelSize: 13
                    color: Theme.colors.textSecondary
                }
            }
        }

        // ── status bar ───────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: statusLabel.implicitHeight + 20
            color: Theme.colors.surface

            Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }

            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.colors.border }

            Label {
                id: statusLabel
                anchors.centerIn: parent
                text: bridge.statusText
                font.pixelSize: 12
                color: Theme.colors.textSecondary
                textFormat: Text.PlainText
                Accessible.role: Accessible.StatusBar
            }
        }
    }

    } // grabRoot

    // Format segmented control: checkable chip, selected state is the web
    // design's accent outline + readable text, visible focus ring. Exclusive
    // through formatGroup.
    component CheckButton: Button {
        id: chip
        property string checkText
        checkable: true
        // Explicit: inline components have been observed to drop out of
        // the Tab chain otherwise, leaving the filter mouse-only.
        activeFocusOnTab: true
        implicitHeight: 28
        implicitWidth: chipLabel.implicitWidth + 26
        font.pixelSize: 13
        hoverEnabled: true

        background: Rectangle {
            radius: 14
            // QML hex colors use ARGB; keep these overlays explicitly RGBA.
            color: Theme.mode === "dark"
                 ? Qt.rgba(1, 1, 1, chip.pressed ? 0.10 : chip.hovered ? 0.05 : 0)
                 : Qt.rgba(0, 0, 0, chip.pressed ? 0.08 : chip.hovered ? 0.04 : 0)
            border.color: chip.visualFocus ? Theme.colors.focusRing
                        : chip.checked ? Theme.colors.accent
                        : Theme.colors.border
            border.width: chip.visualFocus ? 2 : 1

            Behavior on color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
            Behavior on border.color { ColorAnimation { duration: Theme.colorMs; easing.type: Easing.OutCubic } }
        }
        contentItem: Label {
            id: chipLabel
            text: chip.checkText
            font.pixelSize: 13
            font.weight: chip.checked ? Font.DemiBold : Font.Medium
            color: chip.checked ? Theme.colors.text : Theme.colors.textSecondary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
}
