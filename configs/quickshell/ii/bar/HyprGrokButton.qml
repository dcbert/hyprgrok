import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.modules.common
import qs.modules.common.widgets

/**
 * HyprGrok status button for the Illogical Impulse top bar (util buttons group).
 *
 * Left-click:   toggle glass panel
 * Right-click:  full interactive Grok Build session
 * Middle-click: analyze focused window
 */
Item {
    id: root

    property string statusText: "Grok"
    property string statusClass: "idle" // idle | active | missing
    property string statusTooltip: "HyprGrok — open panel"
    property int runningSessions: 0
    property bool grokFound: true

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function refresh() {
        statusProc.running = true;
    }

    function runHyprgrok(subcommand) {
        Quickshell.execDetached([
            "bash", "-lc",
            `export PATH="$HOME/.local/bin:$PATH"; ` +
            `if [ -x "$HOME/.local/bin/hyprgrok" ]; then exec "$HOME/.local/bin/hyprgrok" ${subcommand}; ` +
            `elif command -v hyprgrok >/dev/null 2>&1; then exec hyprgrok ${subcommand}; ` +
            `else notify-send -a HyprGrok "HyprGrok" "hyprgrok not found — reinstall or add ~/.local/bin to PATH"; fi`
        ]);
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Process {
        id: statusProc
        command: [
            "bash", "-lc",
            `export PATH="$HOME/.local/bin:$PATH"; ` +
            `if [ -x "$HOME/.local/bin/hyprgrok" ]; then "$HOME/.local/bin/hyprgrok" status --waybar; ` +
            `elif command -v hyprgrok >/dev/null 2>&1; then hyprgrok status --waybar; ` +
            `else echo '{"text":"Grok?","class":"missing","tooltip":"hyprgrok not installed — run install.sh","sessions":{"running":0},"grok_found":false}'; fi`
        ]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text.trim());
                    root.statusText = data.text || "Grok";
                    root.statusClass = data.class || data.alt || "idle";
                    root.statusTooltip = data.tooltip || "HyprGrok";
                    root.runningSessions = (data.sessions && data.sessions.running) ? data.sessions.running : 0;
                    root.grokFound = data.grok_found !== false;
                } catch (e) {
                    root.statusText = "Grok?";
                    root.statusClass = "missing";
                    root.statusTooltip = "Could not read HyprGrok status";
                    root.runningSessions = 0;
                    root.grokFound = false;
                }
            }
        }
    }

    CircleUtilButton {
        id: button
        anchors.centerIn: parent

        onClicked: root.runHyprgrok("toggle")
        altAction: () => root.runHyprgrok("session")
        middleClickAction: () => root.runHyprgrok("ask-window")

        colBackground: root.statusClass === "active"
            ? (Appearance.colors.colSecondaryContainer || Appearance.colors.colLayer2)
            : Appearance.colors.colLayer2
        colBackgroundHover: Appearance.colors.colLayer2Hover
        colRipple: Appearance.colors.colLayer2Active

        // Only one default content child allowed
        MaterialSymbol {
            id: icon
            anchors.centerIn: parent
            horizontalAlignment: Qt.AlignHCenter
            fill: root.statusClass === "active" ? 1 : 0
            text: root.statusClass === "missing" ? "error" : "smart_toy"
            iconSize: Appearance.font.pixelSize.large
            color: {
                if (root.statusClass === "missing")
                    return Appearance.colors.colError || "#f7768e";
                if (root.statusClass === "active")
                    return Appearance.m3colors.m3onSecondaryContainer || Appearance.colors.colOnLayer2;
                return Appearance.colors.colOnLayer2;
            }
        }
    }

    // Badge outside button content slot
    Rectangle {
        visible: root.runningSessions > 0
        anchors {
            right: button.right
            top: button.top
        }
        z: 2
        radius: Appearance.rounding.full
        color: Appearance.colors.colPrimary || Appearance.m3colors.m3primary
        implicitHeight: Math.max(badgeText.implicitWidth, badgeText.implicitHeight) + 2
        implicitWidth: implicitHeight

        StyledText {
            id: badgeText
            anchors.centerIn: parent
            text: root.runningSessions > 9 ? "9+" : String(root.runningSessions)
            font.pixelSize: Appearance.font.pixelSize.smallest
            color: Appearance.m3colors.m3onPrimary || "#fff"
        }
    }

    StyledToolTip {
        extraVisibleCondition: false
        alternativeVisibleCondition: button.hovered
        text: {
            let lines = [root.statusTooltip];
            lines.push("");
            lines.push("Left-click: open / close panel");
            lines.push("Right-click: full Grok session");
            lines.push("Middle-click: analyze focused window");
            if (!root.grokFound)
                lines.push("\n⚠ Official grok CLI not found");
            return lines.join("\n");
        }
    }
}
