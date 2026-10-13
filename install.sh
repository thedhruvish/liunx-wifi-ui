#!/usr/bin/env bash
# ==============================================================================
# Linux Wi-Fi & Bluetooth UI Manager - Installer
# Installs application to standard Linux software locations (/opt/wifi-ui or ~/.local)
# ==============================================================================

set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if installing system-wide (root/sudo) or user-space
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/opt/wifi-ui"
    BIN_DIR="/usr/local/bin"
    APP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor"
    AUTOSTART_DIR="/etc/xdg/autostart"
    echo "==> Installing system-wide to ${INSTALL_DIR}..."
else
    INSTALL_DIR="${HOME}/.local/share/wifi-ui"
    BIN_DIR="${HOME}/.local/bin"
    APP_DIR="${HOME}/.local/share/applications"
    ICON_DIR="${HOME}/.local/share/icons/hicolor"
    AUTOSTART_DIR="${HOME}/.config/autostart"
    echo "==> Installing user-space to ${INSTALL_DIR}..."
fi

# 1. Create target directories
mkdir -p "${INSTALL_DIR}"
mkdir -p "${BIN_DIR}"
mkdir -p "${APP_DIR}"
mkdir -p "${ICON_DIR}/scalable/apps"
mkdir -p "${ICON_DIR}/128x128/apps"

# 2. Copy application files
echo "==> Copying application files..."
cp -r "${SOURCE_DIR}"/*.py "${INSTALL_DIR}/"
cp -r "${SOURCE_DIR}/assets" "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/main.py"

# 3. Create launcher symlink
echo "==> Creating binary symlink in ${BIN_DIR}/wifi-ui..."
ln -sf "${INSTALL_DIR}/main.py" "${BIN_DIR}/wifi-ui"

# 4. Install icons
echo "==> Installing icons..."
if [ -f "${INSTALL_DIR}/assets/app-icon.svg" ]; then
    cp "${INSTALL_DIR}/assets/app-icon.svg" "${ICON_DIR}/scalable/apps/wifi-bluetooth-manager.svg"
fi
if [ -f "${INSTALL_DIR}/assets/app-icon-128.png" ]; then
    cp "${INSTALL_DIR}/assets/app-icon-128.png" "${ICON_DIR}/128x128/apps/wifi-bluetooth-manager.png"
fi

# 5. Install desktop application launcher
echo "==> Installing desktop entry..."
DESKTOP_SRC="${SOURCE_DIR}/wifi-bluetooth-manager.desktop"
cp "${DESKTOP_SRC}" "${APP_DIR}/wifi-bluetooth-manager.desktop"
chmod +x "${APP_DIR}/wifi-bluetooth-manager.desktop"

# 6. If user desktop exists, install desktop shortcut
TARGET_USER_HOME="${HOME}"
if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER}" ]; then
    TARGET_USER_HOME=$(getent passwd "${SUDO_USER}" | cut -d: -f6)
fi

DESKTOP_DIR="${TARGET_USER_HOME}/Desktop"
if [ -d "${DESKTOP_DIR}" ]; then
    echo "==> Creating shortcut on Desktop: ${DESKTOP_DIR}/wifi-bluetooth-manager.desktop..."
    DESKTOP_FILE="${DESKTOP_DIR}/wifi-bluetooth-manager.desktop"
    cp "${DESKTOP_SRC}" "${DESKTOP_FILE}"
    chmod +x "${DESKTOP_FILE}"
    if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER}" ]; then
        chown "${SUDO_USER}:${SUDO_USER}" "${DESKTOP_FILE}"
    fi
    # Mark trusted in XFCE if gio and sha256sum are available
    if command -v gio >/dev/null 2>&1 && command -v sha256sum >/dev/null 2>&1; then
        CHECKSUM=$(sha256sum "${DESKTOP_FILE}" | awk '{print $1}')
        gio set -t string "${DESKTOP_FILE}" metadata::xfce-exe-checksum "${CHECKSUM}" 2>/dev/null || true
    fi
fi

# 7. Update caches if available
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${APP_DIR}" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${ICON_DIR}" 2>/dev/null || true

echo ""
echo "=================================================================="
echo "✔ Installation completed successfully!"
echo "  Run command: wifi-ui"
echo "  Or click 'Wi-Fi & Bluetooth Manager' from your Applications menu"
echo "=================================================================="
