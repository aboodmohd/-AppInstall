import os
import sys
import tempfile
from pathlib import Path

repo, output, page, width, theme = sys.argv[1:]
sys.path.insert(0, repo)
with tempfile.TemporaryDirectory(prefix="appinstall-ux-") as scratch:
    scratch = Path(scratch)
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        path = scratch / key
        path.mkdir()
        os.environ[key] = str(path)
    os.environ["APPINSTALL_UI_DARK"] = str(int(theme == "dark"))
    os.environ["APPINSTALL_DISABLE_UPDATE_TIMER"] = "1"
    from PySide6 import QtCore, QtGui, QtQml, QtTest, QtWidgets
    import manager_qml as ui
    import update_engine

    app = QtWidgets.QApplication(["appinstall-ui-evidence"])
    anchor = QtWidgets.QWidget()
    bridge = ui.Bridge(anchor)
    names = [
        ("Hayase", "appimage", True), ("OpenCode", "appimage", True),
        ("qBittorrent", "appimage", True), ("Stremio", "flatpak", True),
        ("example", "deb", False), ("olliEcode", "appimage", False),
    ]
    launcher = scratch / "fixture.desktop"
    launcher.write_text("[Desktop Entry]\nType=Application\nName=Fixture\nExec=/usr/bin/true\n")
    inventory = [dict(key=f"{fmt}:{name}", name=name, format=fmt, version="1.0",
                      status="installed" if healthy else "stale",
                      desktop=str(launcher) if healthy else "",
                      problems=[] if healthy else ["Launcher and installation record missing"])
                 for name, fmt, healthy in names]
    for row, icon in zip(inventory, ("video-x-generic", "utilities-terminal",
                                    "folder-download", "applications-multimedia")):
        image = QtGui.QIcon.fromTheme(icon).pixmap(64)
        path = scratch / f"{icon}.png"
        if image.save(str(path)):
            row["icon"] = str(path)
    bridge.model.refresh_inventory(inventory)
    bridge._status_text = "Manage favorites, details and removal from an app’s menu."
    entries = [
        ("Firefox", "Fast, private browsing", "Internet"),
        ("VLC Media Player", "Play audio and video in nearly any format.", "Multimedia"),
        ("Bottles", "Run Windows applications in bottles.", "Utilities"),
        ("Brave", "Private browsing with built-in protection.", "Internet"),
        ("Discord", "Voice and text for your communities.", "Internet"),
        ("Spotify", "Music and podcasts for every mood.", "Multimedia"),
        ("darktable", "A photography workflow and RAW developer.", "Graphics"),
        ("Google Chrome", "Browse the web with Chrome.", "Internet"),
        ("Krita", "Open-source painting for artists.", "Graphics"),
        ("Bazaar", "Discover and manage Flatpak applications.", "Utilities"),
        ("qBittorrent", "A cross-platform BitTorrent client.", "Internet"),
    ]
    bridge._catalog_all = [
        dict(name=name, summary=summary, category=category, appId=f"org.fixture.App{i}",
             source="Flatpak", popularity=len(entries) - i)
        for i, (name, summary, category) in enumerate(entries)
    ]
    bridge._rebuild_catalog_view()
    bridge._catalog_featured.replace(bridge._catalog_all[:3])
    bridge.updatesModel.replace_results(inventory, [
        update_engine.UpdateCandidate(
            key=row["key"], format=row["format"], installed_version="1.0",
            state="error" if row["status"] == "stale" else
                  "up-to-date" if row["name"] in ("qBittorrent", "Stremio") else "manual-required",
            reason="Record needs repair before checking updates." if row["status"] == "stale"
                   else "No recognized update information." if row["name"] in ("Hayase", "OpenCode")
                   else "No updates reported.")
        for row in inventory
    ])
    bridge._app_update_status = "The last check found no updates ready to install."
    engine = QtQml.QQmlApplicationEngine()
    engine.addImportPath(str(ui.QML_DIR.parent))
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("appsModel", bridge.model)
    engine.load(str(ui.QML_DIR / "main.qml"))
    window = engine.rootObjects()[0]
    window.resize(int(width), 900 if int(width) > 800 else 650)
    window.setProperty("discoverSelected", page == "discover")
    window.setProperty("updatesSelected", page == "updates")
    if page == "updates":
        bridge.updatesModel.setFilter("error" if theme == "error" else "all")
    if os.environ.get("APPINSTALL_DESKTOP_SMOKE") == "1":
        window.setProperty("discoverRequested", True)
        window.setProperty("updatesRequested", True)
        QtTest.QTest.qWait(350)
        context = QtQml.qmlContext(window)

        def evaluate(code):
            expression = QtQml.QQmlExpression(context, window, code)
            result, undefined = expression.evaluate()
            assert not expression.hasError(), expression.error().toString()
            return result

        evaluate("menuToggle.forceActiveFocus()")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(180)
        assert evaluate("appMenuBar.visible")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Escape)
        QtTest.QTest.qWait(180)
        assert not evaluate("appMenuBar.visible")
        evaluate("discoverTab.forceActiveFocus()")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(180)
        assert evaluate("discoverPanel.visible") and evaluate("catalogList.columns") >= 2
        evaluate("categoryStrip.forceActiveFocus()")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(180)
        assert evaluate("categoryStrip.popup.visible")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Escape)
        QtTest.QTest.qWait(180)
        evaluate("updatesTab.forceActiveFocus()")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(180)
        assert evaluate("applicationUpdatesPage.visible")
        assert bridge.updatesModel.availableCount == 0
        assert bridge.updatesModel.manualCount == bridge.updatesModel.attentionCount == 2
        evaluate("managedTab.forceActiveFocus()")
        QtTest.QTest.keyClick(window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(180)
        assert evaluate("contentArea.visible") and bridge.model.count == 6
        print("PASS: native keyboard navigation, Menu, catalog dropdown, update counts and inventory")
    print(app.platformName(), window.width(), window.height(), window.devicePixelRatio(), flush=True)
    QtCore.QTimer.singleShot(650, lambda: QtCore.QMetaObject.invokeMethod(
        window, "saveWindowShot", QtCore.Q_ARG("QVariant", output)))
    QtCore.QTimer.singleShot(5000, app.quit)
    app.exec()
    if not Path(output).is_file():
        raise SystemExit("Screenshot was not captured")
