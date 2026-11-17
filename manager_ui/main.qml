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
    property bool menuExpanded: true
    property bool filtersExpanded: true
    property bool discoverSelected: false
    property bool discoverRequested: false
    property bool updatesSelected: false
    property bool updatesRequested: false
    property string updateFilter: "all"
    property string catalogSource: "Flatpak"

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

        // ── one-row header: menus and install actions share one line ──
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 62
            color: Theme.colors.surface
            border.color: Theme.colors.border
            border.width: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 7

                Label {
                    text: qsTr("My Applications")
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }

                Button {
                    id: menuToggle
                    objectName: "menuToggle"
                    text: window.menuExpanded ? qsTr("Hide menu") : qsTr("Show menu")
                    onClicked: window.menuExpanded = !window.menuExpanded
                    Accessible.name: text
                    font.pixelSize: 12
                    implicitHeight: 30
                    implicitWidth: contentItem.implicitWidth + 18
                    background: Rectangle {
                        radius: 7
                        color: menuToggle.hovered ? Theme.colors.hover : "transparent"
                        border.color: menuToggle.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: 1
                    }
                    contentItem: Label {
                        text: menuToggle.text
                        color: Theme.colors.textSecondary
                        font: menuToggle.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Explicit RowLayout ensures the four navigation actions remain
                // side by side on KDE and other Qt Quick desktop styles.
                // Only the menu *contents* pop down; tabs never stack vertically.
                RowLayout {
                    id: appMenuBar
                    objectName: "appMenuBar"
                    visible: window.menuExpanded
                    Layout.alignment: Qt.AlignVCenter
                    Layout.preferredWidth: implicitWidth
                    spacing: 2

                    HeaderMenuButton {
                        id: viewMenuButton
                        objectName: "viewMenuButton"
                        text: qsTr("View")
                        onClicked: viewMenuPopup.popup(viewMenuButton, 0, height + 4)
                        Menu {
                            id: viewMenuPopup
                            MenuItem {
                                objectName: "menuRefresh"
                                text: qsTr("Refresh Applications")
                                onTriggered: bridge.refresh()
                            }
                            MenuItem {
                                objectName: "menuFocusSearch"
                                text: qsTr("Focus Search")
                                onTriggered: {
                                    window.filtersExpanded = true
                                    searchField.forceActiveFocus()
                                }
                            }
                            MenuItem {
                                text: window.filtersExpanded ? qsTr("Hide Filters") : qsTr("Show Filters")
                                onTriggered: window.filtersExpanded = !window.filtersExpanded
                            }
                        }
                    }

                    HeaderMenuButton {
                        id: toolsMenuButton
                        objectName: "toolsMenuButton"
                        text: qsTr("Tools")
                        onClicked: toolsMenuPopup.popup(toolsMenuButton, 0, height + 4)
                        Menu {
                            id: toolsMenuPopup
                            MenuItem {
                                text: qsTr("Check for AppInstall Updates")
                                enabled: bridge.actionVisible && bridge.updateTag === ""
                                onTriggered: bridge.checkUpdates(true)
                            }
                            MenuItem {
                                text: qsTr("Application Diagnostics")
                                onTriggered: bridge.openDiagnostics("")
                            }
                        }
                    }

                    HeaderMenuButton {
                        id: settingsMenuButton
                        objectName: "settingsMenuButton"
                        text: qsTr("Settings")
                        onClicked: settingsDialog.open()
                        Accessible.name: qsTr("Open AppInstall Settings")
                    }

                    HeaderMenuButton {
                        id: helpMenuButton
                        objectName: "helpMenuButton"
                        text: qsTr("Help")
                        onClicked: helpMenuPopup.popup(helpMenuButton, 0, height + 4)
                        Menu {
                            id: helpMenuPopup
                            MenuItem {
                                objectName: "menuAbout"
                                text: qsTr("About AppInstall…")
                                onTriggered: aboutDialog.open()
                            }
                            MenuItem {
                                text: qsTr("View Project on GitHub")
                                onTriggered: Qt.openUrlExternally("https://github.com/aboodmohd/-AppInstall")
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true; Layout.minimumWidth: 2 }

                Button {
                    id: filtersToggle
                    objectName: "filtersToggle"
                    text: window.filtersExpanded ? qsTr("Hide filters") : qsTr("Show filters")
                    onClicked: window.filtersExpanded = !window.filtersExpanded
                    Accessible.name: text
                    font.pixelSize: 12
                    implicitHeight: 30
                    implicitWidth: contentItem.implicitWidth + 18
                    background: Rectangle {
                        radius: 7
                        color: filtersToggle.hovered ? Theme.colors.hover : "transparent"
                        border.color: filtersToggle.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: 1
                    }
                    contentItem: Label {
                        text: filtersToggle.text
                        font: filtersToggle.font
                        color: Theme.colors.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // One install dropdown replaces the two separate file/URL buttons.
                Button {
                    id: installDropdown
                    objectName: "installDropdown"
                    text: qsTr("Install  ▾")
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    implicitHeight: 32
                    implicitWidth: contentItem.implicitWidth + 26
                    onClicked: installMenu.popup(installDropdown, 0, installDropdown.height + 4)
                    Accessible.name: qsTr("Install an application")
                    background: Rectangle {
                        radius: 8
                        color: installDropdown.pressed ? Qt.darker(Theme.colors.accent, 1.12)
                             : Theme.colors.accent
                    }
                    contentItem: Label {
                        text: installDropdown.text
                        color: Theme.colors.accentText
                        font: installDropdown.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    Menu {
                        id: installMenu
                        MenuItem {
                            objectName: "menuInstallFile"
                            text: qsTr("Install from File…")
                            onTriggered: bridge.installFromFile()
                        }
                        MenuItem {
                            objectName: "menuInstallUrl"
                            text: qsTr("Install from URL…")
                            onTriggered: bridge.installFromUrl()
                        }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.colors.border }

        // Navigation is separate from the horizontal View / Tools / Settings /
        // Help header. The installed-app manager remains intact and unchanged.
        RowLayout {
            id: pageNavigation
            objectName: "pageNavigation"
            Layout.fillWidth: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            Layout.topMargin: 12
            Layout.bottomMargin: 4
            spacing: 10

            HeaderMenuButton {
                id: managedTab
                objectName: "managedTab"
                text: qsTr("My Applications")
                font.weight: (!window.discoverSelected && !window.updatesSelected)
                             ? Font.DemiBold : Font.Normal
                onClicked: {
                    window.discoverSelected = false
                    window.updatesSelected = false
                }
                Accessible.name: text
            }
            HeaderMenuButton {
                id: discoverTab
                objectName: "discoverTab"
                text: qsTr("Discover Apps")
                font.weight: window.discoverSelected ? Font.DemiBold : Font.Normal
                onClicked: {
                    window.discoverSelected = true
                    window.updatesSelected = false
                    if (!window.discoverRequested) {
                        window.discoverRequested = true
                        bridge.searchCatalog("")
                    }
                }
                Accessible.name: text
            }
            HeaderMenuButton {
                id: updatesTab
                objectName: "updatesTab"
                text: qsTr("Updates")
                font.weight: window.updatesSelected ? Font.DemiBold : Font.Normal
                onClicked: {
                    window.discoverSelected = false
                    window.updatesSelected = true
                    if (!window.updatesRequested) {
                        window.updatesRequested = true
                        bridge.checkApplicationUpdates(true)
                    }
                }
                Accessible.name: qsTr("Managed application updates")
            }
            Item { Layout.fillWidth: true }
            Label {
                text: qsTr("Flathub")
                color: Theme.colors.textSecondary
                font.pixelSize: 12
                visible: window.discoverSelected
            }
        }

        // Filters can be collapsed without hiding the update banner or apps.
        ColumnLayout {
            id: filtersPanel
            objectName: "filtersPanel"
            visible: window.filtersExpanded && !window.discoverSelected && !window.updatesSelected
            Layout.fillWidth: true
            spacing: 0

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
            // Explicit button and popup rather than ComboBox: KDE's style
            // must not intercept the dropdown activation or delegate selection.
            Button {
                id: statusFilter
                property int selectedIndex: 0
                readonly property var options: [
                    { label: qsTr("All statuses"), value: "all" },
                    { label: qsTr("Installed"), value: "installed" },
                    { label: qsTr("Needs repair"), value: "needs-repair" },
                    { label: qsTr("Files missing"), value: "missing" },
                    { label: qsTr("Stale record"), value: "stale" },
                    { label: qsTr("Corrupted"), value: "corrupted" }
                ]
                text: options[selectedIndex].label + " ▾"
                font.pixelSize: 13
                implicitHeight: 32
                implicitWidth: contentItem.implicitWidth + 22
                activeFocusOnTab: true
                Accessible.name: qsTr("Status selection")
                function choose(index) {
                    if (index < 0 || index >= options.length) return
                    selectedIndex = index
                    appsModel.setStatusFilter(options[index].value)
                    statusPopup.close()
                }
                Component.onCompleted: appsModel.setStatusFilter(options[selectedIndex].value)
                onClicked: statusPopup.open()

                background: Rectangle {
                    radius: 7
                    color: Theme.colors.surface
                    border.color: statusFilter.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                    border.width: statusFilter.visualFocus ? 2 : 1
                }
                contentItem: Label {
                    text: statusFilter.text
                    font: statusFilter.font
                    color: Theme.colors.text
                    leftPadding: 10
                    rightPadding: 10
                    verticalAlignment: Text.AlignVCenter
                }

                Popup {
                    id: statusPopup
                    x: 0
                    y: statusFilter.height + 4
                    width: Math.max(statusFilter.width, 174)
                    height: statusFilter.options.length * 34 + topPadding + bottomPadding
                    padding: 4
                    focus: true
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    property int keyboardIndex: statusFilter.selectedIndex
                    onOpened: {
                        keyboardIndex = statusFilter.selectedIndex
                        statusChoices.forceActiveFocus()
                    }
                    background: Rectangle {
                        radius: 8
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                    }
                    contentItem: Column {
                        id: statusChoices
                        focus: true
                        Keys.onPressed: (event) => {
                            if (event.key === Qt.Key_Down) {
                                statusPopup.keyboardIndex = (statusPopup.keyboardIndex + 1) % statusFilter.options.length
                                event.accepted = true
                            } else if (event.key === Qt.Key_Up) {
                                statusPopup.keyboardIndex =
                                    (statusPopup.keyboardIndex + statusFilter.options.length - 1) % statusFilter.options.length
                                event.accepted = true
                            } else if (event.key === Qt.Key_Return
                                       || event.key === Qt.Key_Enter
                                       || event.key === Qt.Key_Space) {
                                statusFilter.choose(statusPopup.keyboardIndex)
                                event.accepted = true
                            }
                        }
                        Repeater {
                            id: statusRepeater
                            model: statusFilter.options
                            delegate: Button {
                                id: optionButton
                                required property int index
                                required property var modelData
                                width: statusPopup.availableWidth
                                implicitHeight: 34
                                height: 34
                                activeFocusOnTab: false
                                text: modelData.label
                                onClicked: statusFilter.choose(index)
                                background: Rectangle {
                                    radius: 5
                                    color: (statusPopup.keyboardIndex === index
                                             || optionButton.hovered)
                                           ? Theme.colors.surfaceAlt : "transparent"
                                }
                                contentItem: Label {
                                    text: optionButton.text
                                    font.pixelSize: 13
                                    color: Theme.colors.text
                                    leftPadding: 9
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Accessible.name: optionButton.text
                            }
                        }
                    }
                }
            }

            // Sort order.
            // Explicit button and popup rather than ComboBox: KDE's style
            // must not intercept the dropdown activation or delegate selection.
            Button {
                id: sortCombo
                property int selectedIndex: 0
                readonly property var options: [
                    { label: qsTr("Name (A–Z)"), value: "name-asc" },
                    { label: qsTr("Name (Z–A)"), value: "name-desc" },
                    { label: qsTr("Recently launched"), value: "recent" },
                    { label: qsTr("Size (largest)"), value: "size" }
                ]
                text: options[selectedIndex].label + " ▾"
                font.pixelSize: 13
                implicitHeight: 32
                implicitWidth: contentItem.implicitWidth + 22
                activeFocusOnTab: true
                Accessible.name: qsTr("Sort selection")
                function choose(index) {
                    if (index < 0 || index >= options.length) return
                    selectedIndex = index
                    appsModel.setSort(options[index].value)
                    sortPopup.close()
                }
                Component.onCompleted: appsModel.setSort(options[selectedIndex].value)
                onClicked: sortPopup.open()

                background: Rectangle {
                    radius: 7
                    color: Theme.colors.surface
                    border.color: sortCombo.visualFocus ? Theme.colors.focusRing : Theme.colors.border
                    border.width: sortCombo.visualFocus ? 2 : 1
                }
                contentItem: Label {
                    text: sortCombo.text
                    font: sortCombo.font
                    color: Theme.colors.text
                    leftPadding: 10
                    rightPadding: 10
                    verticalAlignment: Text.AlignVCenter
                }

                Popup {
                    id: sortPopup
                    x: 0
                    y: sortCombo.height + 4
                    width: Math.max(sortCombo.width, 174)
                    height: sortCombo.options.length * 34 + topPadding + bottomPadding
                    padding: 4
                    focus: true
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    property int keyboardIndex: sortCombo.selectedIndex
                    onOpened: {
                        keyboardIndex = sortCombo.selectedIndex
                        sortChoices.forceActiveFocus()
                    }
                    background: Rectangle {
                        radius: 8
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                    }
                    contentItem: Column {
                        id: sortChoices
                        focus: true
                        Keys.onPressed: (event) => {
                            if (event.key === Qt.Key_Down) {
                                sortPopup.keyboardIndex = (sortPopup.keyboardIndex + 1) % sortCombo.options.length
                                event.accepted = true
                            } else if (event.key === Qt.Key_Up) {
                                sortPopup.keyboardIndex =
                                    (sortPopup.keyboardIndex + sortCombo.options.length - 1) % sortCombo.options.length
                                event.accepted = true
                            } else if (event.key === Qt.Key_Return
                                       || event.key === Qt.Key_Enter
                                       || event.key === Qt.Key_Space) {
                                sortCombo.choose(sortPopup.keyboardIndex)
                                event.accepted = true
                            }
                        }
                        Repeater {
                            id: sortRepeater
                            model: sortCombo.options
                            delegate: Button {
                                id: optionButton
                                required property int index
                                required property var modelData
                                width: sortPopup.availableWidth
                                implicitHeight: 34
                                height: 34
                                activeFocusOnTab: false
                                text: modelData.label
                                onClicked: sortCombo.choose(index)
                                background: Rectangle {
                                    radius: 5
                                    color: (sortPopup.keyboardIndex === index
                                             || optionButton.hovered)
                                           ? Theme.colors.surfaceAlt : "transparent"
                                }
                                contentItem: Label {
                                    text: optionButton.text
                                    font.pixelSize: 13
                                    color: Theme.colors.text
                                    leftPadding: 9
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Accessible.name: optionButton.text
                            }
                        }
                    }
                }
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

        } // filtersPanel

        // ── update banner ────────────────────────────────────────────
        Rectangle {
            id: updateBanner
            // Visible whenever there is something to act on: an available
            // tag, a running check/install, or the last status line.
            visible: !window.discoverSelected && !window.updatesSelected && (bridge.updateTag !== "" || bridge.updateStatus !== "")
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

        // ── Discover Apps: responsive store cards and source switching ──
        ColumnLayout {
            id: discoverPanel
            objectName: "discoverPanel"
            visible: window.discoverSelected
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            Layout.bottomMargin: 10
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 7

                Button {
                    id: flatpakSourceButton
                    objectName: "flatpakSourceButton"
                    text: qsTr("Flatpak")
                    font.bold: window.catalogSource === "Flatpak"
                    onClicked: {
                        window.catalogSource = "Flatpak"
                        bridge.searchCatalog(catalogSearchField.text, "Flatpak")
                    }
                }
                Button {
                    id: appimageSourceButton
                    objectName: "appimageSourceButton"
                    text: qsTr("AppImage")
                    font.bold: window.catalogSource === "AppImage"
                    onClicked: {
                        window.catalogSource = "AppImage"
                        bridge.searchCatalog(catalogSearchField.text, "AppImage")
                    }
                }
                Button {
                    id: debSourceButton
                    objectName: "debSourceButton"
                    text: qsTr("DEB")
                    font.bold: window.catalogSource === "DEB"
                    onClicked: {
                        window.catalogSource = "DEB"
                        bridge.searchCatalog(catalogSearchField.text, "DEB")
                    }
                }
                Button {
                    id: rpmSourceButton
                    objectName: "rpmSourceButton"
                    text: qsTr("RPM")
                    font.bold: window.catalogSource === "RPM"
                    onClicked: {
                        window.catalogSource = "RPM"
                        bridge.searchCatalog(catalogSearchField.text, "RPM")
                    }
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: window.catalogSource === "Flatpak" ? "Flathub"
                          : window.catalogSource === "AppImage" ? "AppImageHub"
                          : window.catalogSource === "DEB" ? "Debian packages"
                          : "Fedora packages"
                    font.pixelSize: 12
                    color: Theme.colors.textSecondary
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                TextField {
                    id: catalogSearchField
                    objectName: "catalogSearchField"
                    Layout.fillWidth: true
                    placeholderText: (window.catalogSource === "DEB" ? qsTr("Search Debian APT packages…")
                             : window.catalogSource === "RPM" ? qsTr("Search Fedora DNF packages…")
                             : qsTr("Search applications, games, tools…"))
                    font.pixelSize: 14
                    color: Theme.colors.text
                    placeholderTextColor: Theme.colors.textSecondary
                    selectByMouse: true
                    implicitHeight: 38
                    onTextChanged: catalogTimer.restart()
                    onAccepted: {
                        catalogTimer.stop()
                        bridge.searchCatalog(text, window.catalogSource)
                    }
                    Keys.onEscapePressed: (event) => {
                        if (text) { text = ""; event.accepted = true }
                    }
                    background: Rectangle {
                        radius: 9
                        color: Theme.colors.surface
                        border.color: catalogSearchField.activeFocus
                                      ? Theme.colors.focusRing : Theme.colors.border
                    }
                    leftPadding: 12
                    rightPadding: 12
                }
                Button {
                    id: catalogRetry
                    objectName: "catalogRetry"
                    text: qsTr("Refresh")
                    enabled: !bridge.catalogLoading
                    onClicked: bridge.searchCatalog(catalogSearchField.text, window.catalogSource)
                    implicitHeight: 36
                }
                Timer {
                    id: catalogTimer
                    interval: 480
                    repeat: false
                    onTriggered: bridge.searchCatalog(catalogSearchField.text, window.catalogSource)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Label {
                    text: qsTr("Discover applications")
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                }
                Item { Layout.fillWidth: true }
                BusyIndicator {
                    running: bridge.catalogLoading
                    visible: running
                    implicitHeight: 23
                    implicitWidth: 23
                }
                Label {
                    text: bridge.catalogStatus
                    color: Theme.colors.textSecondary
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.maximumWidth: 430
                    textFormat: Text.PlainText
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                GridView {
                    id: catalogList
                    objectName: "catalogList"
                    anchors.fill: parent
                    visible: !bridge.catalogSetupRequired
                    property int columns: Math.max(1, Math.floor(width / 280))
                    cellWidth: Math.floor(width / columns)
                    cellHeight: 206
                    model: bridge.catalogModel
                    clip: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        id: catalogCard
                        width: catalogList.cellWidth - 12
                        height: catalogList.cellHeight - 8
                        radius: 12
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 13
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 11
                                Rectangle {
                                    Layout.preferredWidth: 53
                                    Layout.preferredHeight: 53
                                    radius: 10
                                    color: Theme.colors.iconFallbackBg
                                    Image {
                                        id: catalogIcon
                                        anchors.fill: parent
                                        anchors.margins: 3
                                        source: model.iconUrl
                                        asynchronous: true
                                        cache: true
                                        fillMode: Image.PreserveAspectFit
                                        visible: status === Image.Ready
                                    }
                                    Label {
                                        anchors.fill: parent
                                        text: updateRow.name.length ? updateRow.name[0].toUpperCase() : "?"
                                        visible: catalogIcon.status !== Image.Ready
                                        color: Theme.colors.textSecondary
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        font.pixelSize: 19
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Label {
                                        Layout.fillWidth: true
                                        text: model.name
                                        textFormat: Text.PlainText
                                        font.pixelSize: 15
                                        font.weight: Font.DemiBold
                                        color: Theme.colors.text
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: model.source === "AppImage" ? "AppImageHub · AppImage"
                                              : model.source === "DEB" ? "Debian · DEB"
                                              : model.source === "RPM" ? "Fedora · RPM"
                                              : "Flathub · Flatpak"
                                        font.pixelSize: 11
                                        color: Theme.colors.textSecondary
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            Label {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: model.summary || model.appId
                                textFormat: Text.PlainText
                                wrapMode: Text.WordWrap
                                elide: Text.ElideRight
                                maximumLineCount: 3
                                font.pixelSize: 12
                                color: Theme.colors.textSecondary
                                verticalAlignment: Text.AlignTop
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    Layout.fillWidth: true
                                    text: model.category || qsTr("Application")
                                    color: Theme.colors.textSecondary
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }
                                Button {
                                    text: model.managed ? qsTr("Managed")
                                        : model.source === "AppImage" && !model.installUrl
                                          ? qsTr("Downloads") : qsTr("Install")
                                    enabled: !model.managed
                                    implicitHeight: 32
                                    implicitWidth: 92
                                    Accessible.name: text + " " + model.name
                                    onClicked: bridge.installCatalogEntry(model.appId, model.source)
                                }
                            }
                        }
                    }
                }

                Label {
                    anchors.centerIn: parent
                    visible: catalogList.visible && bridge.catalogModel.count === 0
                             && !bridge.catalogLoading
                    text: bridge.catalogStatus
                    color: Theme.colors.textSecondary
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    width: Math.min(parent.width - 32, 440)
                    horizontalAlignment: Text.AlignHCenter
                    textFormat: Text.PlainText
                }

                ColumnLayout {
                    id: repositorySetupPanel
                    objectName: "repositorySetupPanel"
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 32, 590)
                    visible: bridge.catalogSetupRequired
                             && (window.catalogSource === "DEB" || window.catalogSource === "RPM")
                    spacing: 16
                    Label {
                        Layout.fillWidth: true
                        text: window.catalogSource === "DEB"
                              ? qsTr("Enable Debian DEB discovery")
                              : qsTr("Enable Fedora RPM discovery")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: Theme.colors.text
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Label {
                        Layout.fillWidth: true
                        text: qsTr("AppInstall searches the official package index inside its managed rootless container. Initial setup downloads a container image and package metadata; it will ask for permission first. Distrobox shares your home and desktop, so it is not a security sandbox.")
                        color: Theme.colors.textSecondary
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        textFormat: Text.PlainText
                    }
                    Button {
                        id: repositoryEnableButton
                        objectName: "repositoryEnableButton"
                        Layout.alignment: Qt.AlignHCenter
                        text: window.catalogSource === "DEB"
                              ? qsTr("Enable Debian repository")
                              : qsTr("Enable Fedora repository")
                        enabled: !bridge.catalogLoading
                        onClicked: bridge.prepareCatalogSource(window.catalogSource, catalogSearchField.text)
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: catalogList.visible && bridge.catalogHasMore
                Item { Layout.fillWidth: true }
                Button {
                    id: catalogViewMore
                    objectName: "catalogViewMore"
                    text: qsTr("View more")
                    enabled: !bridge.catalogLoading
                    onClicked: bridge.loadMoreCatalog()
                    implicitWidth: 150
                }
                Item { Layout.fillWidth: true }
            }
        }

        // ── Updates: AppInstall-managed applications, not the application itself ──
        ColumnLayout {
            id: applicationUpdatesPage
            objectName: "applicationUpdatesPage"
            visible: window.updatesSelected
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            Layout.topMargin: 10
            Layout.bottomMargin: 12
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Label {
                        text: qsTr("Application Updates")
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                        color: Theme.colors.text
                        Accessible.role: Accessible.Heading
                    }
                    Label {
                        text: qsTr("Check your managed Flatpak, DEB, RPM and AppImage apps. Nothing updates automatically.")
                        font.pixelSize: 12
                        color: Theme.colors.textSecondary
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                    }
                }
                BusyIndicator {
                    running: bridge.appUpdatesBusy
                    visible: running
                    implicitHeight: 25
                    implicitWidth: 25
                }
                Button {
                    id: appUpdateCheckButton
                    objectName: "appUpdateCheckButton"
                    text: bridge.appImagePreparing ? qsTr("Downloading…")
                          : bridge.appUpdatesBusy ? qsTr("Checking…") : qsTr("Check now")
                    enabled: !bridge.appUpdatesBusy && !bridge.appUpdateRunning
                    onClicked: bridge.checkApplicationUpdates(true)
                    Accessible.name: qsTr("Check for application updates")
                }
                Button {
                    id: appUpdateCancelCheck
                    objectName: "appUpdateCancelCheck"
                    visible: bridge.appUpdatesBusy && !bridge.appUpdateRunning && !bridge.appImagePreparing
                    text: qsTr("Cancel check")
                    onClicked: bridge.cancelApplicationUpdateCheck()
                }
                Button {
                    id: appUpdateCancelInstall
                    objectName: "appUpdateCancelInstall"
                    visible: bridge.flatpakUpdateRunning
                    text: qsTr("Stop update")
                    onClicked: bridge.cancelRunningFlatpakUpdate()
                }
            }

            Flow {
                id: updatesFilters
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: [
                        { label: qsTr("All"), value: "all" },
                        { label: qsTr("Available"), value: "available" },
                        { label: qsTr("Up to date"), value: "up-to-date" },
                        { label: qsTr("Manual"), value: "manual-required" },
                        { label: qsTr("Unsupported"), value: "unsupported" },
                        { label: qsTr("Errors"), value: "error" }
                    ]
                    delegate: Button {
                        id: updateFilterButton
                        required property var modelData
                        text: modelData.label
                        font.pixelSize: 12
                        checked: window.updateFilter === modelData.value
                        checkable: true
                        implicitHeight: 31
                        onClicked: {
                            window.updateFilter = modelData.value
                            bridge.updatesModel.setFilter(modelData.value)
                        }
                        Accessible.name: qsTr("Show updates: ") + modelData.label
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: bridge.appUpdatesStatus
                    textFormat: Text.PlainText
                    color: Theme.colors.textSecondary
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
                Label {
                    text: qsTr("%1 available").arg(bridge.updatesModel.availableCount)
                    color: Theme.colors.text
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
            }

            ListView {
                id: appUpdatesList
                objectName: "appUpdatesList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: bridge.updatesModel
                clip: true
                spacing: 8
                activeFocusOnTab: false
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: updateRow
                    // Qt 6: declaring a required "index" property disables
                    // the old context-property injection of model roles.
                    // Declare every used role explicitly so text and action
                    // eligibility are bound to the real QAbstractListModel.
                    required property int index
                    required property string key
                    required property string name
                    required property string format
                    required property string updateState
                    required property string currentVersion
                    required property string availableVersion
                    required property string reason
                    required property bool actionable
                    // Expose *rendered* labels and action state to the QML
                    // regression test through ListView.itemAtIndex().
                    readonly property string renderedTitle: updateTitle.text
                    readonly property string renderedVersion: updateVersion.text
                    readonly property string renderedState: updateStateLabel.text
                    readonly property bool reviewVisible: reviewUpdateAction.visible
                    objectName: "updateAppRow"
                    width: appUpdatesList.width - 8
                    height: 116
                    radius: 10
                    color: Theme.colors.surface
                    border.color: Theme.colors.border
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12
                        Rectangle {
                            width: 44
                            height: 44
                            radius: 9
                            color: Theme.colors.iconFallbackBg
                            Layout.alignment: Qt.AlignVCenter
                            Label {
                                anchors.centerIn: parent
                                text: updateRow.name.length ? updateRow.name[0].toUpperCase() : "?"
                                color: Theme.colors.textSecondary
                                font.pixelSize: 17
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Label {
                                id: updateTitle
                                objectName: "updateAppTitle"
                                Layout.fillWidth: true
                                text: updateRow.name + " · " + updateRow.format
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                color: Theme.colors.text
                                textFormat: Text.PlainText
                            }
                            Label {
                                id: updateVersion
                                objectName: "updateAppVersion"
                                Layout.fillWidth: true
                                text: updateRow.currentVersion + "  →  " + updateRow.availableVersion
                                font.pixelSize: 12
                                color: Theme.colors.textSecondary
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: updateRow.reason
                                font.pixelSize: 11
                                color: Theme.colors.textSecondary
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                maximumLineCount: 2
                                wrapMode: Text.WordWrap
                            }
                        }
                        ColumnLayout {
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 6
                            Label {
                                id: updateStateLabel
                                objectName: "updateAppState"
                                text: updateRow.updateState
                                color: updateRow.updateState === "available"
                                       ? Theme.colors.success : Theme.colors.textSecondary
                                font.pixelSize: 11
                                Layout.alignment: Qt.AlignRight
                            }
                            Button {
                                text: updateRow.format === "AppImage"
                                      ? qsTr("Download & review")
                                      : qsTr("Review update")
                                objectName: "reviewFlatpakUpdateButton"
                                id: reviewUpdateAction
                                visible: updateRow.actionable && updateRow.updateState === "available"
                                enabled: !bridge.appUpdatesBusy && !bridge.appUpdateRunning
                                onClicked: bridge.requestManagedUpdate(updateRow.key)
                                Accessible.name: qsTr("Review update for ") + updateRow.name
                            }
                        }
                    }
                }
            }

            Label {
                visible: bridge.updatesModel.count === 0 && !bridge.appUpdatesBusy
                Layout.fillWidth: true
                text: qsTr("No applications in this filter. Use Check now or select All.")
                color: Theme.colors.textSecondary
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                textFormat: Text.PlainText
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: bridge.appUpdateProgress ? 82 : 0
                visible: bridge.appUpdateProgress !== ""
                clip: true
                TextArea {
                    objectName: "appUpdateProgressOutput"
                    text: bridge.appUpdateProgress
                    readOnly: true
                    wrapMode: Text.WrapAnywhere
                    selectByMouse: true
                    font.pixelSize: 11
                    color: Theme.colors.text
                    textFormat: TextEdit.PlainText
                }
            }
        }

        // ── list ─────────────────────────────────────────────────────
        Item {
            id: contentArea
            objectName: "contentArea"
            visible: !window.discoverSelected && !window.updatesSelected
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
                text: window.updatesSelected ? bridge.appUpdatesStatus
                    : window.discoverSelected ? bridge.catalogStatus : bridge.statusText
                font.pixelSize: 12
                color: Theme.colors.textSecondary
                textFormat: Text.PlainText
                Accessible.role: Accessible.StatusBar
            }
        }
    }

    } // grabRoot

    // Working preferences stored atomically in ~/.local/share/appinstall/settings.json.
    // Every change passes through the existing settings sanitizer; no dummy toggles.
    Dialog {
        id: settingsDialog
        objectName: "settingsDialog"
        title: qsTr("AppInstall Settings")
        modal: true
        standardButtons: Dialog.Close
        width: Math.min(window.width - 48, 475)
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)

        background: Rectangle {
            radius: 12
            color: Theme.colors.surface
            border.color: Theme.colors.border
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 10

            Label {
                text: qsTr("Appearance")
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.colors.text
            }
            ButtonGroup { id: appearanceChoice }
            RadioButton {
                text: qsTr("Follow system theme")
                ButtonGroup.group: appearanceChoice
                checked: bridge.themeChoice === "auto"
                onClicked: bridge.setTheme("auto")
                Accessible.name: text
            }
            RadioButton {
                text: qsTr("Light")
                ButtonGroup.group: appearanceChoice
                checked: bridge.themeChoice === "light"
                onClicked: bridge.setTheme("light")
            }
            RadioButton {
                text: qsTr("Dark")
                ButtonGroup.group: appearanceChoice
                checked: bridge.themeChoice === "dark"
                onClicked: bridge.setTheme("dark")
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.colors.border }

            Label {
                text: qsTr("Notifications")
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.colors.text
            }
            CheckBox {
                id: notificationCheck
                objectName: "notificationCheck"
                text: qsTr("Notify me about available AppInstall updates")
                checked: bridge.notificationsEnabled
                onClicked: bridge.setNotificationsEnabled(checked)
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.colors.border }

            Label {
                text: qsTr("Default uninstall choice")
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.colors.text
            }
            ButtonGroup { id: uninstallChoice }
            RadioButton {
                objectName: "uninstallAsk"
                text: qsTr("Ask every time (remove app only by default)")
                ButtonGroup.group: uninstallChoice
                checked: bridge.uninstallMode === "ask"
                onClicked: bridge.setUninstallMode("ask")
            }
            RadioButton {
                objectName: "uninstallAppOnly"
                text: qsTr("Remove app only")
                ButtonGroup.group: uninstallChoice
                checked: bridge.uninstallMode === "app_only"
                onClicked: bridge.setUninstallMode("app_only")
            }
            RadioButton {
                objectName: "uninstallWithData"
                text: qsTr("Remove app + verified AppInstall history")
                ButtonGroup.group: uninstallChoice
                checked: bridge.uninstallMode === "with_managed_data"
                onClicked: bridge.setUninstallMode("with_managed_data")
            }
            Label {
                text: qsTr("Every uninstall still asks for confirmation. Personal folders, downloads and shared containers are always kept.")
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: Theme.colors.textSecondary
            }
            Label {
                text: qsTr("Preferences are saved as you change them.")
                Layout.fillWidth: true
                font.pixelSize: 12
                color: Theme.colors.textSecondary
            }
        }
    }

    // Lightweight about dialog; no hardcoded version or unverified claims.
    Dialog {
        id: aboutDialog
        objectName: "aboutAppInstallDialog"
        title: qsTr("About AppInstall")
        modal: true
        standardButtons: Dialog.Close
        width: Math.min(window.width - 48, 420)
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)

        background: Rectangle {
            radius: 12
            color: Theme.colors.surface
            border.color: Theme.colors.border
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 12
            Label {
                text: qsTr("AppInstall")
                font.pixelSize: 22
                font.weight: Font.DemiBold
                color: Theme.colors.text
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("An open-source Linux app installer and manager for AppImage, Flatpak, DEB, and RPM.")
                wrapMode: Text.WordWrap
                font.pixelSize: 13
                color: Theme.colors.textSecondary
            }
        }
    }

    // A conventional header tab, but laid out explicitly in a single row.
    component HeaderMenuButton: Button {
        id: headerNav
        implicitHeight: 32
        implicitWidth: headerNavLabel.implicitWidth + 18
        font.pixelSize: 13
        hoverEnabled: true
        activeFocusOnTab: true
        background: Rectangle {
            radius: 7
            color: headerNav.down ? Theme.colors.pressed
                 : headerNav.hovered ? Theme.colors.hover : "transparent"
            border.color: headerNav.visualFocus ? Theme.colors.focusRing : "transparent"
            border.width: headerNav.visualFocus ? 2 : 0
        }
        contentItem: Label {
            id: headerNavLabel
            text: headerNav.text
            color: Theme.colors.text
            font: headerNav.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

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
