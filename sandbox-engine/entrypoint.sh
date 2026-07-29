#!/bin/bash
set -e

# Setup display environment variables
export DISPLAY=:1
export SCREEN_WIDTH=${SCREEN_WIDTH:-1280}
export SCREEN_HEIGHT=${SCREEN_HEIGHT:-800}
export SCREEN_DEPTH=24

echo "[OpenDesktop Sandbox] Starting Xvfb virtual framebuffer on $DISPLAY (${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH})..."
Xvfb $DISPLAY -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} -ac &
XVFB_PID=$!
sleep 2

# Populate desktop launchers in both /root/Desktop and /home/agent/Desktop
mkdir -p /root/Desktop /home/agent/Desktop

cat << 'EOF' > /root/Desktop/Google-Chrome.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Google Chrome
Exec=google-chrome-stable --no-sandbox --disable-gpu %U
Icon=google-chrome
Terminal=false
Categories=Network;WebBrowser;
EOF

cat << 'EOF' > /root/Desktop/VS-Code.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=VS Code
Exec=code --no-sandbox --user-data-dir=/root/.vscode-data %F
Icon=vscode
Terminal=false
Categories=Development;IDE;
EOF

cat << 'EOF' > /root/Desktop/Obsidian.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Obsidian
Exec=obsidian --no-sandbox /root/ObsidianVault %U
Icon=obsidian
Terminal=false
Categories=Office;
EOF

cat << 'EOF' > /root/Desktop/Hermes-Desktop.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Hermes Desktop
Exec=xfce4-terminal --working-directory=/home/agent/Projects/hermes-desktop
Icon=system-run
Terminal=false
Categories=Development;
EOF

cp -r /root/Desktop/* /home/agent/Desktop/ 2>/dev/null || true
chmod +x /root/Desktop/*.desktop /home/agent/Desktop/*.desktop 2>/dev/null || true

# Trust desktop launchers so XFCE displays icon titles cleanly without prompt
if command -v gio >/dev/null 2>&1; then
    for desktop_file in /root/Desktop/*.desktop /home/agent/Desktop/*.desktop; do
        if [ -f "$desktop_file" ]; then
            gio trust "$desktop_file" 2>/dev/null || true
        fi
    done
fi

echo "[OpenDesktop Sandbox] Starting XFCE4 desktop..."
dbus-launch --exit-with-session xfce4-session &
XFCE_PID=$!
sleep 3

echo "[OpenDesktop Sandbox] Starting x11vnc..."
x11vnc -display $DISPLAY -forever -shared -nopw -rfbport 5900 -quiet -bg &
sleep 1

echo "[OpenDesktop Sandbox] Starting noVNC WebSocket proxy on port 6080..."
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "[OpenDesktop Sandbox] Starting Agent Control Daemon on port 8000..."
python3 /app/agent_daemon.py &
DAEMON_PID=$!

echo "[OpenDesktop Sandbox] All services ready. Desktop sandbox is live with Chrome, VS Code, Obsidian, Hermes Desktop & Claude Code!"

# Keep container alive
trap 'kill $XVFB_PID $XFCE_PID $DAEMON_PID 2>/dev/null; exit 0' SIGTERM SIGINT

wait $DAEMON_PID
