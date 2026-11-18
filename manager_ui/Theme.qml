pragma Singleton
import QtQuick

QtObject {
    // mode: "light" | "dark" — main.qml syncs this from bridge.dark once at
    // startup and on theme changes. reducedMotion disables all movement;
    // color transitions remain (they aid comprehension, Emil's reduced-motion
    // rule: fewer and gentler, not zero).
    property string mode: "light"
    property bool reducedMotion: false

    // Motion tokens. Durations follow Emil's table: hover/color 160ms,
    // press 120ms, entrances 240ms, all OutCubic. Keyboard-initiated
    // actions never animate.
    readonly property int colorMs: reducedMotion ? 0 : 160
    readonly property int pressMs: reducedMotion ? 0 : 120
    readonly property int enterMs: reducedMotion ? 0 : 240
    readonly property int staggerMs: reducedMotion ? 0 : 40

    // Qt parses 8-digit hex colors as #AARRGGBB, not CSS #RRGGBBAA.
    // The old dark hover #ffffff0d accidentally rendered opaque yellow.
    readonly property var light: ({
        window:    "#F5F7FB",
        header:    "#FFFFFF",
        surface:   "#ffffff",
        surfaceAlt:"#EFF3F9",
        border:    "#DCE3EE",
        text:      "#132033",
        textSecondary: "#5E6F85",
        accent:    "#4166E8",
        accentText:"#ffffff",
        focusRing: "#4166E8",
        success:   "#137E58",
        successBg: "#1a137e58",
        warning:   "#93600F",
        warningBg: "#1a93600f",
        danger:    "#b3402e",
        dangerBg:  "#1ab3402e",
        neutral:   "#5f5f66",
        neutralBg: "#145f5f66",
        hover:     "#0a000000",
        pressed:   "#14000000",
        iconFallbackBg: "#E2EAFD",
        shadow:    "#0f000000",
    })

    readonly property var dark: ({
        window:    "#0B1018",
        header:    "#101722",
        surface:   "#141D29",
        surfaceAlt:"#1A2534",
        border:    "#293749",
        text:      "#EFF4FC",
        textSecondary: "#9DAFC4",
        accent:    "#7293FF",
        accentText:"#0B1018",
        focusRing: "#7293FF",
        success:   "#55E0B1",
        successBg: "#2455e0b1",
        warning:   "#F3BF75",
        warningBg: "#24f3bf75",
        danger:    "#f28b82",
        dangerBg:  "#24f28b82",
        neutral:   "#a7a7b0",
        neutralBg: "#1fa7a7b0",
        hover:     "#0dffffff",
        pressed:   "#1affffff",
        iconFallbackBg: "#25365A",
        shadow:    "#40000000",
    })

    readonly property var colors: mode === "dark" ? dark : light

    function tone(toneName) {
        switch (toneName) {
        case 'success': return colors.success
        case 'warning': return colors.warning
        case 'danger':  return colors.danger
        default:        return colors.neutral
        }
    }

    function toneBg(toneName) {
        switch (toneName) {
        case 'success': return colors.successBg
        case 'warning': return colors.warningBg
        case 'danger':  return colors.dangerBg
        default:        return colors.neutralBg
        }
    }
}
