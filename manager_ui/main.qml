import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
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
    palette.window: Theme.colors.header
    palette.windowText: Theme.colors.text
    palette.base: Theme.colors.surface
    palette.text: Theme.colors.text
    palette.button: Theme.colors.surfaceAlt
    palette.buttonText: Theme.colors.text
    palette.highlight: Theme.colors.iconFallbackBg
    palette.highlightedText: Theme.colors.text
    property bool filtersExpanded: true
    property bool advancedFilters: false
    readonly property int pageInset: Math.max(20, Math.round(width * 0.044))
    readonly property int scrollGap: 6
    property bool discoverSelected: false
    property bool discoverRequested: false
    property bool updatesSelected: false
    property bool updatesRequested: false
    property string updateFilter: "all"
    property string catalogSource: "Flatpak"

    function showManaged() {
        discoverSelected = false
        updatesSelected = false
    }

    function showDiscover() {
        discoverSelected = true
        updatesSelected = false
        if (!discoverRequested) {
            discoverRequested = true
            bridge.searchCatalog("")
        }
    }

    function showUpdates() {
        discoverSelected = false
        updatesSelected = true
        if (!updatesRequested) {
            updatesRequested = true
            bridge.checkApplicationUpdates(true)
        }
    }

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
        appsModel.groupLibrary()
        Theme.reducedMotion = bridge.reducedMotion
        Theme.mode = bridge.dark ? "dark" : "light"
        searchField.forceActiveFocus()
    }

    Connections {
        target: bridge
        function onDarkChanged() { Theme.mode = bridge.dark ? "dark" : "light" }
        function onCatalogViewportReset() {
            catalogList.schedulePosition(0)
            featuredStrip.page = 0
        }
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
            implicitHeight: 76
            color: Theme.colors.header
            border.color: Theme.colors.border
            border.width: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: window.pageInset
                anchors.rightMargin: anchors.leftMargin
                spacing: 12

                Rectangle {
                    implicitWidth: 38
                    implicitHeight: 38
                    radius: 11
                    color: Theme.colors.iconFallbackBg
                    Label {
                        anchors.centerIn: parent
                        text: "A"
                        font.pixelSize: 21
                        font.bold: true
                        color: Theme.colors.accent
                    }
                }

                Label {
                    text: qsTr("AppInstall")
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }

                RowLayout {
                    id: pageNavigation
                    objectName: "pageNavigation"
                    spacing: 4

                    HeaderMenuButton {
                        id: managedTab
                        objectName: "managedTab"
                        text: qsTr("My apps")
                        highlighted: !window.discoverSelected && !window.updatesSelected
                        onClicked: window.showManaged()
                    }
                    HeaderMenuButton {
                        id: discoverTab
                        objectName: "discoverTab"
                        text: qsTr("Discover")
                        highlighted: window.discoverSelected
                        onClicked: window.showDiscover()
                    }
                    HeaderMenuButton {
                        id: updatesTab
                        objectName: "updatesTab"
                        text: qsTr("Updates")
                        highlighted: window.updatesSelected
                        onClicked: window.showUpdates()
                    }
                }

                Item { Layout.fillWidth: true }

                Button {
                    id: menuToggle
                    objectName: "menuToggle"
                    text: qsTr("Menu")
                    onClicked: appMenuBar.popup(menuToggle, 0, height + 4)
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

                Menu {
                    id: appMenuBar
                    objectName: "appMenuBar"

                    Menu {
                        objectName: "viewMenuButton"
                        title: qsTr("View")
                            MenuItem {
                                objectName: "menuRefresh"
                                text: qsTr("Refresh Applications")
                                onTriggered: bridge.refresh()
                            }
                            MenuItem {
                                text: qsTr("Refresh Discover")
                                visible: window.discoverSelected
                                enabled: !bridge.catalogLoading
                                onTriggered: bridge.searchCatalog(catalogSearchField.text, window.catalogSource)
                            }
                            MenuItem {
                                objectName: "menuFocusSearch"
                                text: qsTr("Focus Search")
                                onTriggered: {
                                    window.showManaged()
                                    window.filtersExpanded = true
                                    searchField.forceActiveFocus()
                                }
                            }
                            MenuItem {
                                text: window.filtersExpanded ? qsTr("Hide Filters") : qsTr("Show Filters")
                                onTriggered: window.filtersExpanded = !window.filtersExpanded
                            }
                    }

                    Menu {
                        objectName: "toolsMenuButton"
                        title: qsTr("Tools & diagnostics")
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

                    MenuItem {
                        objectName: "settingsMenuButton"
                        text: qsTr("Settings")
                        onTriggered: settingsDialog.open()
                        Accessible.name: qsTr("Open AppInstall Settings")
                    }

                    Menu {
                        objectName: "helpMenuButton"
                        title: qsTr("Help")
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

                // One install dropdown replaces the two separate file/URL buttons.
                Button {
                    id: installDropdown
                    objectName: "installDropdown"
                    text: qsTr("Install app")
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                implicitHeight: 44
                    implicitWidth: contentItem.implicitWidth + 26
                    onClicked: installMenu.popup(installDropdown, 0, installDropdown.height + 4)
                    Accessible.name: qsTr("Install an application")
                    background: Rectangle {
                        radius: 11
                        color: installDropdown.pressed ? Qt.darker(Theme.colors.accent, 1.12)
                             : Theme.colors.accent
                        border.width: installDropdown.visualFocus ? 2 : 0
                        border.color: Theme.colors.text
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
                        MenuItem {
                            text: qsTr("Discover apps")
                            onTriggered: window.showDiscover()
                        }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.colors.border }

        ColumnLayout {
            visible: !window.discoverSelected && !window.updatesSelected
            Layout.fillWidth: true
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.topMargin: 24
            spacing: 6
            Label {
                text: qsTr("My applications")
                font.pixelSize: 34
                font.weight: Font.Bold
                color: Theme.colors.text
                Accessible.role: Accessible.Heading
            }
            Label {
                text: qsTr("Open and manage the applications you’ve installed.")
                font.pixelSize: 14
                color: Theme.colors.textSecondary
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
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.topMargin: 14
            Layout.bottomMargin: 8
            spacing: 10

            // Search: the primary control, prominent and always visible.
            TextField {
                id: searchField
                Layout.fillWidth: true
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

            SurfaceComboBox {
                Accessible.name: qsTr("Filter applications by package format")
                textRole: "label"
                valueRole: "value"
                model: [
                    {label: qsTr("All formats"), value: "all"},
                    {label: "AppImage", value: "appimage"},
                    {label: "Flatpak", value: "flatpak"},
                    {label: "DEB", value: "deb"},
                    {label: "RPM", value: "rpm"}
                ]
                onActivated: appsModel.setFormatFilter(currentValue)
            }

            // Status filter.
            // Explicit button and popup rather than ComboBox: KDE's style
            // must not intercept the dropdown activation or delegate selection.
            Button {
                id: statusFilter
                visible: window.advancedFilters
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
            HeaderMenuButton {
                text: qsTr("Filters")
                highlighted: window.advancedFilters || statusFilter.selectedIndex !== 0
                Accessible.description: qsTr("Show or hide the status filter")
                onClicked: window.advancedFilters = !window.advancedFilters
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

        Rectangle {
            visible: contentArea.visible && appsModel.attentionCount > 0
            Layout.fillWidth: true
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.topMargin: 4
            Layout.bottomMargin: 4
            implicitHeight: 44
            radius: 11
            color: Theme.colors.warningBg
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                Label {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: appsModel.attentionCount === 1
                          ? qsTr("1 application needs your attention")
                          : qsTr("%1 applications need your attention").arg(appsModel.attentionCount)
                    color: Theme.colors.warning
                    font.weight: Font.DemiBold
                }
                HeaderMenuButton {
                    text: qsTr("Review issues")
                    onClicked: appList.focusCard(appsModel.count - appsModel.attentionCount)
                }
            }
        }

        // ── update banner ────────────────────────────────────────────
        Rectangle {
            id: updateBanner
            // Visible whenever there is something to act on: an available
            // tag, a running check/install, or the last status line.
            visible: !window.discoverSelected && !window.updatesSelected && (bridge.updateTag !== "" || bridge.updateStatus !== "")
            Layout.fillWidth: true
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.bottomMargin: 6
            implicitHeight: 32
            radius: 9
            color: "transparent"

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
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.bottomMargin: 10
            spacing: 10

            ColumnLayout {
                visible: !bridge.catalogDetailsAvailable
                Layout.topMargin: 24
                Layout.bottomMargin: 10
                spacing: 6
                Label {
                    text: qsTr("Discover something great")
                    font.pixelSize: 34
                    font.bold: true
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }
                Label {
                    text: qsTr("Browse apps across Flatpak, AppImage, DEB and RPM.")
                    font.pixelSize: 14
                    color: Theme.colors.textSecondary
                }
            }

            // Compact, centered store-style details — no new network requests.
            ColumnLayout {
                id: catalogDetailsPage
                objectName: "catalogDetailsPage"
                visible: bridge.catalogDetailsAvailable
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                ScrollView {
                    id: catalogDetailsScroll
                    objectName: "catalogDetailsScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    Item {
                        width: catalogDetailsScroll.availableWidth
                        implicitHeight: detailsContent.implicitHeight + 20

                        ColumnLayout {
                            id: detailsContent
                            objectName: "catalogDetailsContent"
                            width: Math.min(parent.width - 16, 1050)
                            x: Math.max(0, (parent.width - width) / 2)
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Button {
                                    id: catalogDetailsBack
                                    objectName: "catalogDetailsBack"
                                    text: qsTr("← Back to Discover")
                                    implicitHeight: 32
                                    onClicked: bridge.closeCatalogDetails()
                                    Accessible.name: qsTr("Back to Discover applications")
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: qsTr("APPLICATION DETAILS")
                                    color: Theme.colors.textSecondary
                                    font.pixelSize: 10
                                    font.letterSpacing: 1.3
                                }
                            }

                            Rectangle {
                                id: catalogDetailsHero
                                objectName: "catalogDetailsHero"
                                Layout.fillWidth: true
                                implicitHeight: 148
                                radius: 14
                                color: Theme.colors.surface
                                border.color: Theme.colors.border
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 16

                                    Rectangle {
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 80
                                        radius: 17
                                        color: Theme.colors.iconFallbackBg
                                        Image {
                                            id: catalogLargeIcon
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            source: bridge.catalogDetails.iconUrl || ""
                                            sourceSize.width: 160
                                            sourceSize.height: 160
                                            asynchronous: true
                                            cache: true
                                            fillMode: Image.PreserveAspectFit
                                            visible: status === Image.Ready
                                        }
                                        Label {
                                            anchors.fill: parent
                                            visible: catalogLargeIcon.status !== Image.Ready
                                            text: bridge.catalogDetails.name
                                                  ? bridge.catalogDetails.name[0].toUpperCase() : "?"
                                            font.pixelSize: 28
                                            color: Theme.colors.textSecondary
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Label {
                                            id: catalogDetailsName
                                            objectName: "catalogDetailsName"
                                            Layout.fillWidth: true
                                            text: bridge.catalogDetails.name || ""
                                            textFormat: Text.PlainText
                                            color: Theme.colors.text
                                            font.pixelSize: 24
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Label {
                                            Layout.fillWidth: true
                                            text: bridge.catalogDetails.developer
                                                  ? qsTr("by %1").arg(bridge.catalogDetails.developer)
                                                  : qsTr("Developer not provided")
                                            textFormat: Text.PlainText
                                            font.pixelSize: 12
                                            color: Theme.colors.textSecondary
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 6
                                            Rectangle {
                                                Layout.preferredWidth: sourceChipLabel.implicitWidth + 18
                                                Layout.preferredHeight: 25
                                                radius: 7
                                                color: Theme.colors.surfaceAlt
                                                Label {
                                                    id: sourceChipLabel
                                                    anchors.centerIn: parent
                                                    text: bridge.catalogDetails.sourceLabel || ""
                                                    color: Theme.colors.textSecondary
                                                    font.pixelSize: 11
                                                    textFormat: Text.PlainText
                                                }
                                            }
                                            Rectangle {
                                                Layout.preferredWidth: categoryChipLabel.implicitWidth + 18
                                                Layout.preferredHeight: 25
                                                radius: 7
                                                color: Theme.toneBg("success")
                                                Label {
                                                    id: categoryChipLabel
                                                    anchors.centerIn: parent
                                                    text: bridge.catalogDetails.categoryGroup || qsTr("Other")
                                                    color: Theme.tone("success")
                                                    font.pixelSize: 11
                                                    textFormat: Text.PlainText
                                                }
                                            }
                                            Item { Layout.fillWidth: true }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.alignment: Qt.AlignVCenter
                                        Layout.preferredWidth: 138
                                        spacing: 8

                                        Button {
                                            id: catalogDetailsInstall
                                            objectName: "catalogDetailsInstall"
                                            Layout.fillWidth: true
                                            implicitHeight: 40
                                            text: bridge.catalogDetails.actionLabel || qsTr("Install")
                                            enabled: !bridge.catalogDetails.managed
                                            onClicked: bridge.installSelectedCatalogEntry()
                                            Accessible.name: text + " " + (bridge.catalogDetails.name || "")
                                            background: Rectangle {
                                                radius: 9
                                                color: catalogDetailsInstall.enabled
                                                       ? (catalogDetailsInstall.down
                                                          ? Theme.colors.pressed
                                                          : Theme.colors.accent)
                                                       : Theme.colors.surfaceAlt
                                            }
                                            contentItem: Label {
                                                text: catalogDetailsInstall.text
                                                color: catalogDetailsInstall.enabled
                                                       ? Theme.colors.accentText
                                                       : Theme.colors.textSecondary
                                                font.pixelSize: 13
                                                font.weight: Font.DemiBold
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                        Button {
                                            id: catalogHomepageButton
                                            objectName: "catalogHomepageButton"
                                            Layout.fillWidth: true
                                            implicitHeight: 35
                                            text: qsTr("Visit website")
                                            visible: Boolean(bridge.catalogDetails.homepage)
                                            onClicked: bridge.openSelectedCatalogHomepage()
                                            Accessible.name: qsTr("Visit application publisher website")
                                        }
                                    }
                                }
                            }

                            GridLayout {
                                id: detailsColumns
                                objectName: "catalogDetailsColumns"
                                Layout.fillWidth: true
                                columns: detailsContent.width >= 780 ? 2 : 1
                                columnSpacing: 12
                                rowSpacing: 12

                                ColumnLayout {
                                    id: detailsLeftColumn
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: detailsContent.width * 0.56
                                    spacing: 12

                                    Rectangle {
                                        id: detailsAboutCard
                                        objectName: "catalogDetailsAboutCard"
                                        Layout.fillWidth: true
                                        implicitHeight: Math.max(116,
                                            catalogDetailsDescription.implicitHeight + 72)
                                        radius: 12
                                        color: Theme.colors.surface
                                        border.color: Theme.colors.border
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 17
                                            spacing: 11
                                            Label {
                                                text: qsTr("About")
                                                font.pixelSize: 15
                                                font.weight: Font.DemiBold
                                                color: Theme.colors.text
                                                Accessible.role: Accessible.Heading
                                            }
                                            Label {
                                                id: catalogDetailsDescription
                                                objectName: "catalogDetailsDescription"
                                                Layout.fillWidth: true
                                                text: bridge.catalogDetails.summary ||
                                                      qsTr("No description has been provided.")
                                                textFormat: Text.PlainText
                                                font.pixelSize: 13
                                                color: Theme.colors.textSecondary
                                                wrapMode: Text.WordWrap
                                                verticalAlignment: Text.AlignTop
                                            }
                                            Item { Layout.fillHeight: true }
                                        }
                                    }

                                    Rectangle {
                                        id: detailsIdentityCard
                                        objectName: "catalogDetailsIdentityCard"
                                        Layout.fillWidth: true
                                        implicitHeight: bridge.catalogDetails.componentId
                                            && bridge.catalogDetails.componentId !== bridge.catalogDetails.appId
                                            ? 157 : 119
                                        radius: 12
                                        color: Theme.colors.surface
                                        border.color: Theme.colors.border
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 9
                                            Label {
                                                text: qsTr("Package information")
                                                font.pixelSize: 15
                                                font.weight: Font.DemiBold
                                                color: Theme.colors.text
                                                Accessible.role: Accessible.Heading
                                            }
                                            Label {
                                                text: qsTr("PACKAGE ID")
                                                font.pixelSize: 10
                                                color: Theme.colors.textSecondary
                                                font.letterSpacing: 0.8
                                            }
                                            TextEdit {
                                                objectName: "catalogDetailsPackageId"
                                                Layout.fillWidth: true
                                                text: bridge.catalogDetails.appId || ""
                                                font.pixelSize: 12
                                                textFormat: TextEdit.PlainText
                                                color: Theme.colors.text
                                                wrapMode: TextEdit.WrapAnywhere
                                                readOnly: true
                                                selectByMouse: true
                                            }
                                            Label {
                                                visible: Boolean(bridge.catalogDetails.componentId)
                                                         && bridge.catalogDetails.componentId !== bridge.catalogDetails.appId
                                                text: qsTr("APPSTREAM ID")
                                                font.pixelSize: 10
                                                color: Theme.colors.textSecondary
                                                font.letterSpacing: 0.8
                                            }
                                            TextEdit {
                                                objectName: "catalogDetailsAppStreamId"
                                                visible: Boolean(bridge.catalogDetails.componentId)
                                                         && bridge.catalogDetails.componentId !== bridge.catalogDetails.appId
                                                Layout.fillWidth: true
                                                text: bridge.catalogDetails.componentId || ""
                                                font.pixelSize: 12
                                                textFormat: TextEdit.PlainText
                                                color: Theme.colors.text
                                                wrapMode: TextEdit.WrapAnywhere
                                                readOnly: true
                                                selectByMouse: true
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    id: detailsFactsCard
                                    objectName: "catalogDetailsFactsCard"
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: detailsContent.width * 0.40
                                    implicitHeight: Math.max(246, detailsFactsLayout.implicitHeight + 34)
                                    radius: 12
                                    color: Theme.colors.surface
                                    border.color: Theme.colors.border

                                    ColumnLayout {
                                        id: detailsFactsLayout
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 17
                                        spacing: 14
                                        Label {
                                            text: qsTr("At a glance")
                                            color: Theme.colors.text
                                            font.pixelSize: 15
                                            font.weight: Font.DemiBold
                                            Accessible.role: Accessible.Heading
                                        }
                                        Repeater {
                                            model: [
                                                { name: qsTr("Category"),
                                                  value: bridge.catalogDetails.categoryGroup || qsTr("Other") },
                                                { name: qsTr("Version"),
                                                  value: bridge.catalogDetails.version || qsTr("Not provided") },
                                                { name: qsTr("License"),
                                                  value: bridge.catalogDetails.licenseDisplay ||
                                                         bridge.catalogDetails.license || qsTr("Not provided") },
                                                { name: qsTr("Developer"),
                                                  value: bridge.catalogDetails.developer || qsTr("Not provided") }
                                            ]
                                            delegate: ColumnLayout {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                spacing: 4
                                                Label {
                                                    text: modelData.name
                                                    color: Theme.colors.textSecondary
                                                    font.pixelSize: 11
                                                    textFormat: Text.PlainText
                                                }
                                                Label {
                                                    Layout.fillWidth: true
                                                    text: modelData.value
                                                    color: Theme.colors.text
                                                    font.pixelSize: 13
                                                    textFormat: Text.PlainText
                                                    wrapMode: Text.WrapAnywhere
                                                    maximumLineCount: 3
                                                    elide: Text.ElideRight
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Information comes from the selected catalog. Missing fields are never guessed. Installation still requires review and confirmation.")
                                color: Theme.colors.textSecondary
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: !bridge.catalogDetailsAvailable
                layoutDirection: Qt.RightToLeft
                spacing: 12

                RowLayout {
                spacing: 4
                HeaderMenuButton {
                    id: flatpakSourceButton
                    objectName: "flatpakSourceButton"
                    text: qsTr("Flatpak")
                    highlighted: window.catalogSource === "Flatpak"
                    onClicked: {
                        window.catalogSource = "Flatpak"
                        bridge.searchCatalog(catalogSearchField.text, "Flatpak")
                    }
                }
                HeaderMenuButton {
                    id: appimageSourceButton
                    objectName: "appimageSourceButton"
                    text: qsTr("AppImage")
                    highlighted: window.catalogSource === "AppImage"
                    onClicked: {
                        window.catalogSource = "AppImage"
                        bridge.searchCatalog(catalogSearchField.text, "AppImage")
                    }
                }
                HeaderMenuButton {
                    id: debSourceButton
                    objectName: "debSourceButton"
                    text: qsTr("DEB")
                    highlighted: window.catalogSource === "DEB"
                    onClicked: {
                        window.catalogSource = "DEB"
                        bridge.searchCatalog(catalogSearchField.text, "DEB")
                    }
                }
                HeaderMenuButton {
                    id: rpmSourceButton
                    objectName: "rpmSourceButton"
                    text: qsTr("RPM")
                    highlighted: window.catalogSource === "RPM"
                    onClicked: {
                        window.catalogSource = "RPM"
                        bridge.searchCatalog(catalogSearchField.text, "RPM")
                    }
                }
                }

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
                    implicitHeight: 48
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
                    parent: catalogHeading
                    objectName: "catalogRetry"
                    text: qsTr("Refresh")
                    visible: !bridge.catalogLoading && bridge.catalogModel.count === 0
                             && !bridge.catalogSetupRequired
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
                id: featuredHeading
                objectName: "featuredHeading"
                Layout.fillWidth: true
                visible: !bridge.catalogDetailsAvailable && bridge.catalogHasFeatured
                spacing: 10
                Label {
                    text: qsTr("Featured apps")
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("From Flathub's live popular collection")
                    font.pixelSize: 11
                    color: Theme.colors.textSecondary
                    elide: Text.ElideRight
                }
                HeaderMenuButton {
                    visible: window.height < 620
                    implicitHeight: 30
                    text: featuredStrip.expandedOnShortWindow ? qsTr("Hide featured") : qsTr("Show featured")
                    onClicked: featuredStrip.expandedOnShortWindow = !featuredStrip.expandedOnShortWindow
                }
                HeaderMenuButton {
                    visible: featuredStrip.visible && featuredStrip.pageCount > 1
                    text: qsTr("Previous")
                    implicitHeight: 30
                    enabled: featuredStrip.page > 0
                    Accessible.name: qsTr("Previous Featured apps")
                    onClicked: featuredStrip.page--
                }
                HeaderMenuButton {
                    visible: featuredStrip.visible && featuredStrip.pageCount > 1
                    text: qsTr("Next")
                    implicitHeight: 30
                    enabled: featuredStrip.page < featuredStrip.pageCount - 1
                    Accessible.name: qsTr("Next Featured apps")
                    onClicked: featuredStrip.page++
                }
            }

            Item {
                id: featuredStrip
                objectName: "featuredStrip"
                property bool expandedOnShortWindow: false
                property int page: 0
                readonly property int cardsPerPage: 3
                readonly property int pageCount: Math.ceil(featuredRepeater.count / cardsPerPage)
                onPageCountChanged: page = Math.max(0, Math.min(page, pageCount - 1))
                Layout.fillWidth: true
                Layout.preferredHeight: window.height < 700 ? 100 : 138
                visible: !bridge.catalogDetailsAvailable && bridge.catalogHasFeatured
                         && (window.height >= 620 || expandedOnShortWindow)
                clip: true
                Row {
                    id: featuredRow
                    spacing: 8
                    x: -featuredStrip.page * (featuredStrip.width + spacing)
                    Repeater {
                        id: featuredRepeater
                        model: bridge.featuredCatalogModel
                        delegate: Rectangle {
                            width: (featuredStrip.width - (featuredStrip.cardsPerPage - 1)
                                    * featuredRow.spacing) / featuredStrip.cardsPerPage
                            height: featuredStrip.height
                            radius: 11
                            color: Theme.colors.surface
                            border.color: Theme.colors.border
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: window.height < 700 ? 9 : 16
                                spacing: 4
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Rectangle {
                                        Layout.preferredWidth: 36
                                        Layout.preferredHeight: 36
                                        radius: 8
                                        color: Theme.colors.iconFallbackBg
                                        Image {
                                            id: featuredIcon
                                            anchors.fill: parent
                                            anchors.margins: 3
                                            source: model.iconUrl
                                            sourceSize.width: 80
                                            sourceSize.height: 80
                                            asynchronous: true
                                            fillMode: Image.PreserveAspectFit
                                            visible: status === Image.Ready
                                        }
                                        Label {
                                            anchors.fill: parent
                                            visible: featuredIcon.status !== Image.Ready
                                            text: model.name.length ? model.name[0].toUpperCase() : "?"
                                            color: Theme.colors.textSecondary
                                            font.pixelSize: 16
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: model.name
                                        textFormat: Text.PlainText
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                        color: Theme.colors.text
                                        elide: Text.ElideRight
                                    }
                                }
                                Label {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    text: model.summary || model.appId
                                    textFormat: Text.PlainText
                                    font.pixelSize: 11
                                    color: Theme.colors.textSecondary
                                    elide: Text.ElideRight
                                    maximumLineCount: 2
                                    wrapMode: Text.WordWrap
                                    verticalAlignment: Text.AlignTop
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label {
                                        Layout.fillWidth: true
                                        text: model.developer || qsTr("Flathub")
                                        textFormat: Text.PlainText
                                        font.pixelSize: 10
                                        color: Theme.colors.textSecondary
                                        elide: Text.ElideRight
                                    }
                                    HeaderMenuButton {
                                        implicitHeight: 28
                                        enabled: Math.floor(index / featuredStrip.cardsPerPage) === featuredStrip.page
                                        text: qsTr("View app")
                                        Accessible.name: qsTr("View details for %1").arg(model.name)
                                        onClicked: bridge.openCatalogDetails(model.appId, model.source)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                id: catalogHeading
                Layout.fillWidth: true
                visible: !bridge.catalogDetailsAvailable
                spacing: 8
                Label {
                    text: qsTr("Browse all apps")
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                }
                Item { Layout.fillWidth: true }
                SurfaceComboBox {
                    id: categoryStrip
                    objectName: "categoryStrip"
                    Accessible.name: qsTr("Catalog category")
                    model: bridge.catalogCategories
                    currentIndex: Math.max(0, bridge.catalogCategories.indexOf(bridge.catalogCategory))
                    onActivated: bridge.chooseCatalogCategory(currentText)
                }
                SurfaceComboBox {
                    Accessible.name: qsTr("Sort catalog results")
                    textRole: "label"
                    valueRole: "value"
                    model: [
                        {label: qsTr("Recommended"), value: "recommended"},
                        {label: qsTr("Name (A–Z)"), value: "name"}
                    ]
                    onActivated: bridge.sortCatalog(currentValue)
                }
                BusyIndicator {
                    running: bridge.catalogLoading
                    visible: running
                    implicitHeight: 23
                    implicitWidth: 23
                }
                Label {
                    text: bridge.catalogLoading ? bridge.catalogStatus : ""
                    visible: text !== ""
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
                visible: !bridge.catalogDetailsAvailable

                GridView {
                    id: catalogList
                    objectName: "catalogList"
                    anchors.fill: parent
                    visible: !bridge.catalogSetupRequired
                    readonly property real gridWidth: width - catalogScrollBar.width - window.scrollGap
                    readonly property int columns: Math.min(4, Math.max(2, Math.floor(gridWidth / 280)))
                    // GridView may refit its visible items after a reset or insert.
                    // Use an offset relative to its origin, not an absolute contentY.
                    property real pendingOffset: -1
                    activeFocusOnTab: false
                    boundsBehavior: Flickable.StopAtBounds
                    function schedulePosition(offset) {
                        pendingOffset = offset
                        Qt.callLater(applyScheduledPosition)
                    }
                    function applyScheduledPosition() {
                        if (pendingOffset < 0 || !visible || height <= 0 || count === 0)
                            return
                        const offset = pendingOffset
                        pendingOffset = -1
                        forceLayout()
                        if (offset === 0)
                            positionViewAtBeginning()
                        else
                            contentY = originY + Math.min(offset, Math.max(0, contentHeight - height))
                    }
                    onVisibleChanged: if (visible) Qt.callLater(applyScheduledPosition)
                    onHeightChanged: if (pendingOffset >= 0) Qt.callLater(applyScheduledPosition)
                    onCountChanged: if (pendingOffset >= 0) Qt.callLater(applyScheduledPosition)
                    Connections {
                        target: bridge.catalogModel
                        function rememberPosition() {
                            if (catalogList.pendingOffset < 0)
                                catalogList.schedulePosition(Math.max(0, catalogList.contentY - catalogList.originY))
                        }
                        function onModelAboutToBeReset() { rememberPosition() }
                        function onRowsAboutToBeInserted() { rememberPosition() }
                    }
                    cellWidth: Math.floor(gridWidth / columns)
                    cellHeight: window.height < 700 ? 146 : 174
                    model: bridge.catalogModel
                    clip: true
                    ScrollBar.vertical: ScrollBar {
                        id: catalogScrollBar
                        policy: ScrollBar.AsNeeded
                    }

                    delegate: Rectangle {
                        id: catalogCard
                        objectName: "catalogCard"
                        readonly property string renderedInitial: catalogFallback.text
                        readonly property bool usingFallback: catalogFallback.visible
                        width: catalogList.cellWidth - 12
                        height: catalogList.cellHeight - 8
                        radius: 12
                        color: cardHover.hovered ? Theme.colors.surfaceAlt : Theme.colors.surface
                        border.color: activeFocus ? Theme.colors.focusRing : Theme.colors.border
                        border.width: 1

                        ToolTip.visible: cardHover.hovered
                        ToolTip.delay: 650
                        ToolTip.text: (model.name || model.appId)
                                      + (model.developer ? "\nDeveloper: " + model.developer : "")
                                      + (model.license ? "\nLicense: " + model.license : "")
                                      + (model.version ? "\nVersion: " + model.version : "")
                                      + "\nSource: " + model.source

                        HoverHandler { id: cardHover }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: bridge.openCatalogDetails(model.appId, model.source)
                        }
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Details for %1").arg(model.name)
                        Accessible.onPressAction: bridge.openCatalogDetails(model.appId, model.source)
                        Keys.onReturnPressed: bridge.openCatalogDetails(model.appId, model.source)
                        Keys.onSpacePressed: bridge.openCatalogDetails(model.appId, model.source)

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 13
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 11
                                Rectangle {
                                    Layout.preferredWidth: 44
                                    Layout.preferredHeight: 44
                                    radius: 10
                                    color: Theme.colors.iconFallbackBg
                                    Image {
                                        id: catalogIcon
                                        anchors.fill: parent
                                        anchors.margins: 3
                                        source: model.iconUrl
                                        sourceSize.width: 96
                                        sourceSize.height: 96
                                        asynchronous: true
                                        cache: true
                                        fillMode: Image.PreserveAspectFit
                                        visible: status === Image.Ready
                                    }
                                    Label {
                                        anchors.fill: parent
                                        id: catalogFallback
                                        objectName: "catalogIconFallback"
                                        text: model.name.length ? model.name[0].toUpperCase() : "?"
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
                                    text: (model.category || qsTr("Application"))
                                          + (model.version ? " · " + model.version : "")
                                    color: Theme.colors.textSecondary
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }
                                HeaderMenuButton {
                                    filled: true
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
                visible: !bridge.catalogDetailsAvailable && catalogList.visible
                         && bridge.catalogHasMore
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
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset
            Layout.topMargin: 24
            Layout.bottomMargin: 12
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: 8
                spacing: 6
                Label {
                    text: qsTr("Application updates")
                    font.pixelSize: 34
                    font.bold: true
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }
                Label {
                    text: qsTr("See what’s available and what needs your attention. Nothing updates automatically.")
                    font.pixelSize: 14
                    color: Theme.colors.textSecondary
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: updateOverview.implicitHeight + 28
                radius: 12
                color: Theme.colors.surface
                border.color: Theme.colors.border
                RowLayout {
                id: updateOverview
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10
                Label {
                    Layout.fillWidth: true
                    text: bridge.appUpdatesStatus
                    textFormat: Text.PlainText
                    color: Theme.colors.text
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                BusyIndicator {
                    running: bridge.appUpdatesBusy
                    visible: running
                    implicitHeight: 25
                    implicitWidth: 25
                }
                HeaderMenuButton {
                    id: appUpdateCheckButton
                    primary: true
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
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: [
                        {label: qsTr("Available updates"), count: bridge.updatesModel.availableCount,
                         color: Theme.colors.success},
                        {label: qsTr("Manual or unsupported"), count: bridge.updatesModel.manualCount,
                         color: Theme.colors.accent},
                        {label: qsTr("Requires attention"), count: bridge.updatesModel.attentionCount,
                         color: Theme.colors.warning}
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 86
                        radius: 12
                        color: Theme.colors.surface
                        border.color: Theme.colors.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 13
                            Label {
                                text: modelData.label
                                color: Theme.colors.textSecondary
                                font.pixelSize: 13
                            }
                            Label {
                                text: modelData.count
                                color: modelData.color
                                font.pixelSize: 27
                                font.bold: true
                            }
                        }
                    }
                }
            }

            RowLayout {
                id: updatesFilters
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Update status")
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.colors.text
                    Accessible.role: Accessible.Heading
                }
                SurfaceComboBox {
                    objectName: "updateStatusFilter"
                    Accessible.name: qsTr("Filter application updates by status")
                    textRole: "label"
                    valueRole: "value"
                    model: [
                        { label: qsTr("All states"), value: "all" },
                        { label: qsTr("Available"), value: "available" },
                        { label: qsTr("Up to date"), value: "up-to-date" },
                        { label: qsTr("Manual"), value: "manual-required" },
                        { label: qsTr("Unsupported"), value: "unsupported" },
                        { label: qsTr("Errors"), value: "error" }
                    ]
                    onActivated: {
                        window.updateFilter = currentValue
                        bridge.updatesModel.setFilter(currentValue)
                    }
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
                ScrollBar.vertical: ScrollBar {
                    id: updatesScrollBar
                    policy: ScrollBar.AsNeeded
                }

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
                    width: appUpdatesList.width - updatesScrollBar.width - window.scrollGap
                    height: 78
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
                                ToolTip.visible: reasonHover.hovered && truncated
                                ToolTip.text: text
                                HoverHandler { id: reasonHover }
                            }
                        }
                        RowLayout {
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 14
                            Label {
                                id: updateStateLabel
                                objectName: "updateAppState"
                                readonly property color tone: updateRow.updateState === "available"
                                    ? Theme.colors.success : updateRow.updateState === "error"
                                    ? Theme.colors.warning : Theme.colors.textSecondary
                                text: ({
                                    "available": qsTr("Available"),
                                    "manual-required": qsTr("Manual check"),
                                    "unsupported": qsTr("Unsupported"),
                                    "up-to-date": qsTr("Up to date"),
                                    "error": qsTr("Needs attention"),
                                    "checking": qsTr("Checking")
                                })[updateRow.updateState] || updateRow.updateState
                                color: tone
                                font.pixelSize: 12
                            }
                            HeaderMenuButton {
                                filled: true
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
                            HeaderMenuButton {
                                filled: true
                                text: qsTr("Review")
                                visible: updateRow.updateState === "error"
                                      || updateRow.updateState === "manual-required"
                                      || updateRow.updateState === "unsupported"
                                Accessible.name: qsTr("Review application record for %1").arg(updateRow.name)
                                onClicked: bridge.showDetails(updateRow.key)
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
            Layout.leftMargin: window.pageInset
            Layout.rightMargin: window.pageInset

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
                section.property: statusFilter.selectedIndex === 0 ? "librarySection" : ""
                section.delegate: Label {
                    required property string section
                    width: appList.width - libraryScrollBar.width - window.scrollGap
                    topPadding: 12
                    bottomPadding: 9
                    text: section === "attention"
                          ? qsTr("Needs attention  ·  %1").arg(appsModel.attentionCount)
                          : qsTr("Installed  ·  %1").arg(appsModel.count - appsModel.attentionCount)
                    color: Theme.colors.text
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                    Accessible.role: Accessible.Heading
                }

                ScrollBar.vertical: ScrollBar {
                    id: libraryScrollBar
                    policy: ScrollBar.AsNeeded
                }

                // No entrance transition: the model resets on every search
                // keystroke and filter change, so a delegate entrance would
                // re-run on high-frequency operations. Cards appear in place;
                // feedback lives in hover/press color and the status line.

                delegate: AppCard {
                    required property int index
                    width: appList.width - libraryScrollBar.width - window.scrollGap
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
    component SurfaceComboBox: Basic.ComboBox {
        id: surfaceCombo
        implicitHeight: 40
        implicitWidth: 144
        leftPadding: 12
        rightPadding: 26
        palette.text: Theme.colors.text
        palette.buttonText: Theme.colors.text
        palette.window: Theme.colors.surface
        palette.base: Theme.colors.surface
        palette.button: Theme.colors.surface
        palette.highlight: Theme.colors.iconFallbackBg
        palette.highlightedText: Theme.colors.text
        contentItem: Label {
            text: surfaceCombo.displayText
            font.pixelSize: 13
            color: Theme.colors.text
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Label {
            x: surfaceCombo.width - width - 12
            anchors.verticalCenter: parent.verticalCenter
            text: "▾"
            color: Theme.colors.textSecondary
        }
        background: Rectangle {
            radius: 9
            color: surfaceCombo.hovered ? Theme.colors.surfaceAlt : Theme.colors.surface
            border.color: surfaceCombo.visualFocus ? Theme.colors.focusRing : Theme.colors.border
            border.width: surfaceCombo.visualFocus ? 2 : 1
        }
    }

    component HeaderMenuButton: Button {
        id: headerNav
        property bool primary: false
        property bool filled: false
        implicitHeight: 42
        implicitWidth: headerNavLabel.implicitWidth + 28
        font.pixelSize: 14
        font.weight: Font.DemiBold
        hoverEnabled: true
        activeFocusOnTab: true
        background: Rectangle {
            radius: 10
            color: headerNav.primary ? (headerNav.enabled ? Theme.colors.accent : Theme.colors.surfaceAlt)
                 : headerNav.down ? Theme.colors.pressed
                 : headerNav.highlighted ? Theme.colors.iconFallbackBg
                 : headerNav.hovered ? Theme.colors.hover
                 : headerNav.filled ? Theme.colors.surfaceAlt : "transparent"
            border.color: headerNav.visualFocus ? Theme.colors.focusRing : "transparent"
            border.width: headerNav.visualFocus ? 2 : 0
        }
        contentItem: Label {
            id: headerNavLabel
            text: headerNav.text
            color: headerNav.primary && headerNav.enabled ? Theme.colors.accentText
                 : headerNav.highlighted || headerNav.filled ? Theme.colors.text : Theme.colors.textSecondary
            font: headerNav.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

}
