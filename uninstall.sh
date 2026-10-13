#!/usr/bin/env bash
# ==============================================================================
# Linux Wi-Fi & Bluetooth UI Manager - Uninstaller
# ==============================================================================

set -e

if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/opt/wifi-ui"
    BIN_FILE="/usr/local/bin/wifi-ui"
    APP_FILE="/usr/share/applications/wifi-bluetooth-manager.desktop"
    AUTOSTART_FILE="/etc/xdg/autostart/wifi-bluetooth-manager.desktop"
    ICON_SVG="/usr/share/icons/hicolor/scalable/apps/wifi-bluetooth-manager.svg"
    ICON_PNG="/usr/share/icons/hicolor/128x128/apps/wifi-bluetooth-manager.png"
else
    INSTALL_DIR="${HOME}/.local/share/wifi-ui"
    BIN_FILE="${HOME}/.local/bin/wifi-ui"
    APP_FILE="${HOME}/.local/share/applications/wifi-bluetooth-manager.desktop"
    AUTOSTART_FILE="${HOME}/.config/autostart/wifi-bluetooth-manager.desktop"
    ICON_SVG="${HOME}/.local/share/icons/hicolor/scalable/apps/wifi-bluetooth-manager.svg"
    ICON_PNG="${HOME}/.local/share/icons/hicolor/128x128/apps/wifi-bluetooth-manager.png"
fi

echo "==> Removing application files..."
rm -rf "${INSTALL_DIR}"
rm -f "${BIN_FILE}"
rm -f "${APP_FILE}"
rm -f "${AUTOSTART_FILE}"
rm -f "${ICON_SVG}" "${ICON_PNG}"
rm -f "${HOME}/Desktop/wifi-bluetooth-manager.desktop"

echo "✔ Wi-Fi & Bluetooth UI Manager uninstalled successfully."
