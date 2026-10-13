"""
Top-Right Speed Button & Tray Indicator Service.
Displays real-time Wi-Fi speed on the top-right panel / desktop.
When clicked, opens the Quick Wi-Fi Dialog tab to switch networks and monitor speed.
"""

import sys
import subprocess
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3
    HAS_APP_INDICATOR = True
except Exception:
    HAS_APP_INDICATOR = False

from backend import WiFiBackend, BluetoothBackend, format_bytes_speed
from quick_dialog import QuickWiFiDialog
from ui_style import apply_app_styles


class FloatingSpeedButton(Gtk.Window):
    """
    Top Header Row Speed Button.
    Positioned directly inside the top header row (y=2, h=26)
    immediately to the left side of the notification bell icon.
    Displays live Wi-Fi speed and opens the Quick Dialog tab on click.
    """
    def __init__(self, on_clicked_cb):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.on_clicked_cb = on_clicked_cb

        self.set_title("Wi-Fi Speed Indicator")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.stick()  # Stay visible across all virtual desktop workspaces
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.get_style_context().add_class('header-speed-pill')

        # Content
        btn = Gtk.Button()
        btn.get_style_context().add_class('header-speed-btn')
        btn.connect('clicked', lambda _: self.on_clicked_cb())

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.icon = Gtk.Image.new_from_icon_name("network-wireless", Gtk.IconSize.MENU)
        self.label = Gtk.Label(label="⚡ Calculating...")
        self.label.get_style_context().add_class('header-speed-text')

        hbox.pack_start(self.icon, False, False, 0)
        hbox.pack_start(self.label, False, False, 0)
        btn.add(hbox)
        self.add(btn)

        self._position_in_header_row()

    def _position_in_header_row(self):
        screen = Gdk.Screen.get_default()
        if screen:
            geom = screen.get_monitor_geometry(0)
            # Notification icon starts at ~1774 on 1920x1080 display.
            # Position this speed pill immediately on its left side at y=2 with 26px height.
            target_x = max(10, geom.width - 362)
            target_y = 2
            self.set_size_request(210, 26)
            self.move(target_x, target_y)

    def update_display(self, speed_str: str, connected: bool):
        if connected:
            self.icon.set_from_icon_name("network-wireless", Gtk.IconSize.MENU)
            self.label.set_text(speed_str)
        else:
            self.icon.set_from_icon_name("network-wireless-offline", Gtk.IconSize.MENU)
            self.label.set_text("Offline")


class SpeedIndicatorService:
    """
    Orchestrates the top-right button, Ayatana AppIndicator, and the Quick Wi-Fi Dialog.
    """
    def __init__(self, enable_floating: bool = True):
        self.wifi_backend = WiFiBackend()
        self.bt_backend = BluetoothBackend()
        self.enable_floating = enable_floating

        apply_app_styles()

        # Dialog instance (lazy-created or singleton)
        self.quick_dialog = None
        self.main_app_window = None

        # Floating button
        self.floating_btn = None
        if self.enable_floating:
            self.floating_btn = FloatingSpeedButton(on_clicked_cb=self.toggle_quick_dialog)
            self.floating_btn.show_all()

        # System tray indicator
        self.indicator = None
        self.status_icon = None
        self._setup_indicator()

        # Polling timer
        self.timer_id = GLib.timeout_add_seconds(1, self.on_timer_tick)
        self.on_timer_tick()

    def _setup_indicator(self):
        if HAS_APP_INDICATOR:
            try:
                self.indicator = AyatanaAppIndicator3.Indicator.new(
                    "wifi_speed_indicator",
                    "network-wireless",
                    AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS
                )
                self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
                self.indicator.set_label("⚡ Calc...", "⚡ 999 Mbit/s")
                self._update_indicator_menu()
                return
            except Exception as e:
                print(f"AyatanaAppIndicator init failed: {e}")

        # Fallback to Gtk.StatusIcon
        try:
            self.status_icon = Gtk.StatusIcon.new_from_icon_name("network-wireless")
            self.status_icon.connect('activate', lambda _: self.toggle_quick_dialog())
            self.status_icon.set_tooltip_text("Wi-Fi Speed Indicator")
        except Exception as e:
            print(f"StatusIcon init failed: {e}")

    def _update_indicator_menu(self):
        if not self.indicator:
            return

        menu = Gtk.Menu()

        # Item 1: Open Quick Dialog
        item_dialog = Gtk.MenuItem(label="📶 Open Wi-Fi Switcher & Speed")
        item_dialog.connect('activate', lambda _: self.toggle_quick_dialog())
        menu.append(item_dialog)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Item 2: Connected Network status
        details = self.wifi_backend.get_connected_details()
        if details:
            ssid = details.get('ssid')
            rate = details.get('rate')
            item_conn = Gtk.MenuItem(label=f"✓ Connected: {ssid} ({rate})")
            item_conn.set_sensitive(False)
            menu.append(item_conn)

            item_disc = Gtk.MenuItem(label="Disconnect Wi-Fi")
            item_disc.connect('activate', lambda _: self._disconnect_wifi())
            menu.append(item_disc)
        else:
            item_conn = Gtk.MenuItem(label="Offline (Not Connected)")
            item_conn.set_sensitive(False)
            menu.append(item_conn)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Item 3: Open Full Settings
        item_settings = Gtk.MenuItem(label="⚙ Full Wi-Fi & Bluetooth Settings")
        item_settings.connect('activate', lambda _: self.open_full_app())
        menu.append(item_settings)

        # Item 4: Toggle Floating Button
        item_float = Gtk.CheckMenuItem(label="Show Top-Right Screen Button")
        item_float.set_active(self.enable_floating)
        def toggle_float_cb(widget):
            self.enable_floating = widget.get_active()
            if self.floating_btn:
                if self.enable_floating:
                    self.floating_btn.show_all()
                else:
                    self.floating_btn.hide()
        item_float.connect('toggled', toggle_float_cb)
        menu.append(item_float)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Item 5: Quit Indicator
        item_quit = Gtk.MenuItem(label="Quit Indicator")
        item_quit.connect('activate', lambda _: Gtk.main_quit())
        menu.append(item_quit)

        menu.show_all()
        self.indicator.set_menu(menu)

    def _disconnect_wifi(self):
        self.wifi_backend.disconnect_network()
        self.on_timer_tick()

    def toggle_quick_dialog(self):
        """Opens or toggles the Quick Wi-Fi Dialog."""
        if self.quick_dialog is None:
            self.quick_dialog = QuickWiFiDialog(
                self.wifi_backend,
                on_open_full_app_cb=self.open_full_app
            )
            self.quick_dialog.show_all()
        else:
            if self.quick_dialog.get_visible():
                self.quick_dialog.hide()
            else:
                self.quick_dialog.refresh_all(rescan=False)
                self.quick_dialog.show_all()
                self.quick_dialog.present()

    def open_full_app(self):
        from app_window import MainWindow
        if self.main_app_window is None:
            self.main_app_window = MainWindow(self.wifi_backend, self.bt_backend)
            self.main_app_window.show_all()
        else:
            self.main_app_window.present()

    def on_timer_tick(self):
        """Called every 1 second to update live speed across widgets."""
        speed_data = self.wifi_backend.get_live_speed()
        details = self.wifi_backend.get_connected_details()

        rx_fmt = speed_data['rx_fmt']
        connected = bool(details)

        if connected:
            rate = details.get('rate', 'N/A')
            speed_label = f"⚡ {rate} (↓ {rx_fmt})"
            short_label = f"{rate}"
        else:
            speed_label = "Wi-Fi Offline"
            short_label = "Offline"

        # Update floating button
        if self.floating_btn and self.enable_floating:
            self.floating_btn.update_display(speed_label, connected)

        # Update Ayatana Indicator
        if self.indicator:
            self.indicator.set_label(short_label, "999 Mbit/s")
            icon_name = "network-wireless" if connected else "network-wireless-offline"
            self.indicator.set_icon_full(icon_name, "Wi-Fi Speed")

        # Update StatusIcon tooltip
        if self.status_icon:
            tooltip = f"Wi-Fi: {details.get('ssid', 'Offline')}\nSpeed: {speed_label}" if details else "Wi-Fi: Offline"
            self.status_icon.set_tooltip_text(tooltip)

        return True


def run_indicator():
    service = SpeedIndicatorService(enable_floating=True)
    Gtk.main()


if __name__ == '__main__':
    run_indicator()
