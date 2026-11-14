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

    readonly property var light: ({
        window:    "#f5f5f7",
        surface:   "#ffffff",
        surfaceAlt:"#ececee",
        border:    "#dcdce0",
        text:      "#1b1b1f",
        textSecondary: "#5f5f66",
        accent:    "#2456d8",
        accentText:"#ffffff",
        focusRing: "#2456d8",
        success:   "#1a7f37",
        successBg: "#1a7f371a",
        warning:   "#8a5a08",
        warningBg: "#a163091a",
        danger:    "#b3402e",
        dangerBg:  "#b3402e1a",
        neutral:   "#5f5f66",
        neutralBg: "#5f5f6614",
        hover:     "#0000000a",
        pressed:   "#00000014",
        iconFallbackBg: "#e4e6ec",
        shadow:    "#0000000f",
    })

    readonly property var dark: ({
        window:    "#141417",
        surface:   "#1d1d21",
        surfaceAlt:"#26262b",
        border:    "#34343a",
        text:      "#f0f0f3",
        textSecondary: "#a7a7b0",
        accent:    "#4d76ee",
        accentText:"#ffffff",
        focusRing: "#8db2ff",
        success:   "#4ade80",
        successBg: "#4ade8024",
        warning:   "#f5c451",
        warningBg: "#f5c45124",
        danger:    "#f28b82",
        dangerBg:  "#f28b8224",
        neutral:   "#a7a7b0",
        neutralBg: "#a7a7b01f",
        hover:     "#ffffff0d",
        pressed:   "#ffffff1a",
        iconFallbackBg: "#2c3040",
        shadow:    "#00000040",
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
