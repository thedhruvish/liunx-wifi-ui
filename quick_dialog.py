"""
Quick Wi-Fi Switch Dialog that opens when clicking the top-right speed button or tray icon.
Shows:
- Real-time Wi-Fi speed meter (Link rate and live download/upload throughput)
- Currently connected Wi-Fi details
- List of all available Wi-Fi networks with signal strengths
- One-click network switching (with password prompt if needed)
- Button to launch the full Wi-Fi & Bluetooth Manager
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from backend import WiFiBackend, format_bytes_speed
from ui_widgets import SignalBarsWidget, NetworkRowWidget, PasswordDialog
from ui_style import apply_app_styles


class QuickWiFiDialog(Gtk.Window):
    def __init__(self, wifi_backend: WiFiBackend, on_open_full_app_cb=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.wifi_backend = wifi_backend
        self.on_open_full_app_cb = on_open_full_app_cb

        self.set_title("Wi-Fi Quick Switch & Speed")
        self.set_default_size(430, 560)
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)
        self.get_style_context().add_class('main-window')

        # Position near top-right
        self._position_top_right()

        self.networks = []
        self.active_details = None
        self.is_scanning = False
        self.timer_id = None

        self._build_ui()
        self.connect('delete-event', self.on_close_clicked)

        # Initial load
        self.refresh_all(rescan=False)
        self.start_live_timer()

    def _position_top_right(self):
        screen = Gdk.Screen.get_default()
        if screen:
            geom = screen.get_monitor_geometry(0)
            target_x = geom.width - 450
            target_y = 36  # below top panel
            self.move(max(10, target_x), max(10, target_y))

    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(14)
        vbox.set_margin_end(14)
        self.add(vbox)

        # Top Bar
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        icon = Gtk.Image.new_from_icon_name("network-wireless", Gtk.IconSize.LARGE_TOOLBAR)
        top_bar.pack_start(icon, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_lbl = Gtk.Label(label="<b>Wi-Fi &amp; Speed Center</b>")
        title_lbl.set_use_markup(True)
        title_lbl.set_halign(Gtk.Align.START)
        sub_lbl = Gtk.Label(label="Live speed & network switcher")
        sub_lbl.set_halign(Gtk.Align.START)
        sub_lbl.get_style_context().add_class('card-subtitle')
        title_box.pack_start(title_lbl, False, False, 0)
        title_box.pack_start(sub_lbl, False, False, 0)
        top_bar.pack_start(title_box, True, True, 0)

        # Open full app button
        full_btn = Gtk.Button(label="Full App ⚙")
        full_btn.get_style_context().add_class('btn-secondary')
        full_btn.set_tooltip_text("Open Full Wi-Fi & Bluetooth Settings")
        full_btn.connect('clicked', self.on_full_app_clicked)
        top_bar.pack_start(full_btn, False, False, 0)

        vbox.pack_start(top_bar, False, False, 0)

        # Connected Card
        self.conn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.conn_card.get_style_context().add_class('card-box-accent')
        vbox.pack_start(self.conn_card, False, False, 0)

        # Speed and Status Display
        conn_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.conn_name_lbl = Gtk.Label(label="Connecting...")
        self.conn_name_lbl.get_style_context().add_class('card-title')
        self.conn_name_lbl.set_halign(Gtk.Align.START)
        conn_header.pack_start(self.conn_name_lbl, True, True, 0)

        self.conn_signal_bars = SignalBarsWidget(0, width=28, height=18)
        conn_header.pack_start(self.conn_signal_bars, False, False, 0)

        self.conn_signal_pct = Gtk.Label(label="0%")
        self.conn_signal_pct.get_style_context().add_class('pill-badge')
        self.conn_signal_pct.get_style_context().add_class('badge-connected')
        conn_header.pack_start(self.conn_signal_pct, False, False, 0)
        self.conn_card.pack_start(conn_header, False, False, 0)

        # Live Speed Grid
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        # Download Speed
        rx_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        rx_lbl = Gtk.Label(label="Download Speed")
        rx_lbl.get_style_context().add_class('card-subtitle')
        rx_lbl.set_halign(Gtk.Align.START)
        self.rx_val_lbl = Gtk.Label(label="↓ 0.0 KB/s")
        self.rx_val_lbl.get_style_context().add_class('speed-tag')
        self.rx_val_lbl.set_halign(Gtk.Align.START)
        rx_box.pack_start(rx_lbl, False, False, 0)
        rx_box.pack_start(self.rx_val_lbl, False, False, 0)
        speed_box.pack_start(rx_box, True, True, 0)

        # Upload Speed
        tx_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        tx_lbl = Gtk.Label(label="Upload Speed")
        tx_lbl.get_style_context().add_class('card-subtitle')
        tx_lbl.set_halign(Gtk.Align.START)
        self.tx_val_lbl = Gtk.Label(label="↑ 0.0 KB/s")
        self.tx_val_lbl.get_style_context().add_class('speed-tag')
        self.tx_val_lbl.set_halign(Gtk.Align.START)
        tx_box.pack_start(tx_lbl, False, False, 0)
        tx_box.pack_start(self.tx_val_lbl, False, False, 0)
        speed_box.pack_start(tx_box, True, True, 0)

        # Link Bitrate
        rate_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        rate_lbl = Gtk.Label(label="Link Bitrate")
        rate_lbl.get_style_context().add_class('card-subtitle')
        rate_lbl.set_halign(Gtk.Align.START)
        self.rate_val_lbl = Gtk.Label(label="⚡ 0 Mbit/s")
        self.rate_val_lbl.get_style_context().add_class('speed-tag')
        self.rate_val_lbl.set_halign(Gtk.Align.START)
        rate_box.pack_start(rate_lbl, False, False, 0)
        rate_box.pack_start(self.rate_val_lbl, False, False, 0)
        speed_box.pack_start(rate_box, True, True, 0)

        self.conn_card.pack_start(speed_box, False, False, 0)

        # IP and Disconnect
        sub_info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ip_lbl = Gtk.Label(label="IP: N/A")
        self.ip_lbl.get_style_context().add_class('card-subtitle')
        self.ip_lbl.set_halign(Gtk.Align.START)
        sub_info_box.pack_start(self.ip_lbl, True, True, 0)

        self.disconnect_btn = Gtk.Button(label="Disconnect")
        self.disconnect_btn.get_style_context().add_class('btn-danger')
        self.disconnect_btn.connect('clicked', self.on_disconnect_clicked)
        sub_info_box.pack_start(self.disconnect_btn, False, False, 0)
        self.conn_card.pack_start(sub_info_box, False, False, 0)

        # Separator & Switcher Title
        sep_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        list_title = Gtk.Label(label="<b>Switch Wi-Fi Connection</b>")
        list_title.set_use_markup(True)
        list_title.set_halign(Gtk.Align.START)
        sep_box.pack_start(list_title, True, True, 0)

        self.rescan_btn = Gtk.Button(label="↻ Refresh")
        self.rescan_btn.get_style_context().add_class('btn-secondary')
        self.rescan_btn.connect('clicked', lambda _: self.refresh_all(rescan=True))
        sep_box.pack_start(self.rescan_btn, False, False, 0)
        vbox.pack_start(sep_box, False, False, 0)

        # Filter entry
        self.filter_entry = Gtk.SearchEntry()
        self.filter_entry.set_placeholder_text("Filter networks...")
        self.filter_entry.connect('search-changed', self.on_filter_changed)
        vbox.pack_start(self.filter_entry, False, False, 0)

        # Scrollable Network List
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_filter_func(self._filter_row)
        scrolled.add(self.listbox)
        vbox.pack_start(scrolled, True, True, 0)

        # Status footer
        self.status_bar = Gtk.Label(label="Ready")
        self.status_bar.get_style_context().add_class('item-detail')
        self.status_bar.set_halign(Gtk.Align.START)
        vbox.pack_start(self.status_bar, False, False, 0)

    def start_live_timer(self):
        if self.timer_id is None:
            self.timer_id = GLib.timeout_add_seconds(1, self.update_live_speed)

    def stop_live_timer(self):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

    def update_live_speed(self):
        speed_data = self.wifi_backend.get_live_speed()
        self.rx_val_lbl.set_text(f"↓ {speed_data['rx_fmt']}")
        self.tx_val_lbl.set_text(f"↑ {speed_data['tx_fmt']}")
        return True

    def refresh_all(self, rescan: bool = False):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.status_bar.set_text("Scanning Wi-Fi networks...")
        self.rescan_btn.set_sensitive(False)

        def worker():
            details = self.wifi_backend.get_connected_details()
            nets = self.wifi_backend.scan_networks(rescan=rescan)
            GLib.idle_add(self._on_scan_complete, details, nets)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_complete(self, details, nets):
        self.is_scanning = False
        self.rescan_btn.set_sensitive(True)
        self.status_bar.set_text(f"Found {len(nets)} Wi-Fi networks")
        self.active_details = details
        self.networks = nets

        # Update Connected Card
        if details:
            self.conn_name_lbl.set_text(f"Connected: {details.get('ssid')}")
            sig = details.get('signal', 0)
            self.conn_signal_bars.set_signal(sig)
            self.conn_signal_pct.set_text(f"{sig}%")
            self.rate_val_lbl.set_text(f"⚡ {details.get('rate', 'N/A')}")
            self.ip_lbl.set_text(f"IP: {details.get('ip4', 'N/A')} • Gateway: {details.get('gateway', 'N/A')}")
            self.disconnect_btn.set_visible(True)
        else:
            self.conn_name_lbl.set_text("No Wi-Fi Connected")
            self.conn_signal_bars.set_signal(0)
            self.conn_signal_pct.set_text("Offline")
            self.rate_val_lbl.set_text("⚡ 0 Mbit/s")
            self.ip_lbl.set_text("Select a network below to connect")
            self.disconnect_btn.set_visible(False)

        # Populate List
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        for net in nets:
            row_widget = NetworkRowWidget(
                net,
                on_connect_cb=self.on_network_connect_request,
                on_disconnect_cb=self.on_disconnect_clicked
            )
            row = Gtk.ListBoxRow()
            row.add(row_widget)
            row.net_info = net
            self.listbox.add(row)

        self.listbox.show_all()

    def _filter_row(self, row):
        query = self.filter_entry.get_text().strip().lower()
        if not query:
            return True
        ssid = row.net_info.get('ssid', '').lower()
        bssid = row.net_info.get('bssid', '').lower()
        return query in ssid or query in bssid

    def on_filter_changed(self, entry):
        self.listbox.invalidate_filter()

    def on_network_connect_request(self, net_info: dict):
        ssid = net_info.get('ssid')
        is_secured = net_info.get('is_secured', False)
        is_saved = net_info.get('is_saved', False)

        # If already saved or open, try connecting directly
        if is_saved or not is_secured:
            self._do_connect(ssid, password=None)
        else:
            # Show password dialog
            dlg = PasswordDialog(self, ssid)
            resp = dlg.run()
            pwd = dlg.get_password()
            dlg.destroy()
            if resp == Gtk.ResponseType.OK:
                if not pwd:
                    self.status_bar.set_text("Password cannot be empty.")
                    return
                self._do_connect(ssid, password=pwd)

    def _do_connect(self, ssid: str, password=None):
        self.status_bar.set_text(f"Connecting to '{ssid}'...")
        self.set_sensitive(False)

        def worker():
            success, msg = self.wifi_backend.connect_network(ssid, password=password)
            GLib.idle_add(self._on_connect_done, success, msg, ssid)

        threading.Thread(target=worker, daemon=True).start()

    def _on_connect_done(self, success: bool, msg: str, ssid: str):
        self.set_sensitive(True)
        if success:
            self.status_bar.set_text(f"Connected to '{ssid}' successfully!")
            self.refresh_all(rescan=False)
        else:
            self.status_bar.set_text(f"Connection failed: {msg}")

    def on_disconnect_clicked(self, *args):
        self.status_bar.set_text("Disconnecting Wi-Fi...")
        def worker():
            success, msg = self.wifi_backend.disconnect_network()
            GLib.idle_add(self._on_disconnect_done, success, msg)
        threading.Thread(target=worker, daemon=True).start()

    def _on_disconnect_done(self, success: bool, msg: str):
        self.status_bar.set_text(msg)
        self.refresh_all(rescan=False)

    def on_full_app_clicked(self, *args):
        if self.on_open_full_app_cb:
            self.on_open_full_app_cb()
        else:
            import os
            import sys
            import subprocess
            main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
            subprocess.Popen([sys.executable, main_script])

    def on_close_clicked(self, widget, event):
        self.hide()
        return True  # Keep window object alive for quick reopen
