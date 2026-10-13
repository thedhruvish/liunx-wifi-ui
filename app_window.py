"""
Main Application Window for Wi-Fi and Bluetooth Manager.
Provides a modern two-tab UI for Wi-Fi and Bluetooth configuration.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from backend import WiFiBackend, BluetoothBackend, format_bytes_speed
from ui_widgets import SignalBarsWidget, NetworkRowWidget, BluetoothRowWidget, PasswordDialog
from ui_style import apply_app_styles
from speed_indicator import FloatingSpeedButton


class MainWindow(Gtk.Window):
    def __init__(self, wifi_backend: WiFiBackend, bt_backend: BluetoothBackend):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.wifi_backend = wifi_backend
        self.bt_backend = bt_backend

        self.set_title("Wi-Fi & Bluetooth Manager")
        self.set_default_size(620, 680)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class('main-window')

        # Load window icon
        try:
            import os
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'app-icon-64.png')
            if os.path.exists(icon_path):
                self.set_icon_from_file(icon_path)
            else:
                self.set_icon_name("network-wireless")
        except Exception:
            pass

        self.current_tab = "wifi"
        self.wifi_networks = []
        self.wifi_details = None
        self.bt_paired = []
        self.bt_nearby = []
        self.is_wifi_scanning = False
        self.is_bt_scanning = False
        self.speed_timer_id = None

        self._build_ui()
        self.connect('destroy', self.on_destroy)

        # Top header row speed pill - shown ONLY while app is open
        try:
            self.header_pill = FloatingSpeedButton(on_clicked_cb=self.present)
            self.header_pill.show_all()
        except Exception:
            self.header_pill = None

        # Initial data refresh
        self.refresh_wifi(rescan=False)
        self.refresh_bluetooth()
        self.start_live_timer()

    def _build_ui(self):
        # Header Bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Network & Bluetooth")
        header.set_subtitle("Debian System Center")

        # Live Speed badge in Header
        self.header_speed_lbl = Gtk.Label(label="⚡ Calculating...")
        self.header_speed_lbl.get_style_context().add_class('pill-badge')
        self.header_speed_lbl.get_style_context().add_class('badge-speed')
        header.pack_end(self.header_speed_lbl)

        # Refresh button with spinner
        self.refresh_spinner = Gtk.Spinner()
        header.pack_end(self.refresh_spinner)

        self.refresh_btn = Gtk.Button()
        refresh_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_btn.set_image(refresh_icon)
        self.refresh_btn.set_tooltip_text("Refresh Networks & Devices")
        self.refresh_btn.connect('clicked', self.on_global_refresh_clicked)
        header.pack_end(self.refresh_btn)

        self.set_titlebar(header)

        # Main Layout
        root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(root_vbox)

        # Top Switcher Bar (Wi-Fi vs Bluetooth)
        switcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        switcher_box.get_style_context().add_class('tab-switcher')
        switcher_box.set_halign(Gtk.Align.CENTER)

        self.tab_wifi_btn = Gtk.Button(label="📶  Wi-Fi Networks")
        self.tab_wifi_btn.get_style_context().add_class('tab-btn')
        self.tab_wifi_btn.get_style_context().add_class('active')
        self.tab_wifi_btn.connect('clicked', lambda _: self.switch_tab("wifi"))
        switcher_box.pack_start(self.tab_wifi_btn, True, True, 0)

        self.tab_bt_btn = Gtk.Button(label="ᛒ  Bluetooth Devices")
        self.tab_bt_btn.get_style_context().add_class('tab-btn')
        self.tab_bt_btn.connect('clicked', lambda _: self.switch_tab("bt"))
        switcher_box.pack_start(self.tab_bt_btn, True, True, 0)

        root_vbox.pack_start(switcher_box, False, False, 4)

        # Stack container for views
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)

        self.wifi_view = self._build_wifi_view()
        self.bt_view = self._build_bt_view()

        self.stack.add_named(self.wifi_view, "wifi")
        self.stack.add_named(self.bt_view, "bt")
        root_vbox.pack_start(self.stack, True, True, 0)

        # Bottom Status Bar
        self.status_bar = Gtk.Label(label="Ready")
        self.status_bar.get_style_context().add_class('item-detail')
        self.status_bar.set_halign(Gtk.Align.START)
        self.status_bar.set_margin_start(16)
        self.status_bar.set_margin_bottom(8)
        root_vbox.pack_start(self.status_bar, False, False, 0)

    # ----------------------------------------------------
    # Wi-Fi Tab View
    # ----------------------------------------------------
    def _build_wifi_view(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Wi-Fi Toggle Bar
        top_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_ctrl.set_margin_start(18)
        top_ctrl.set_margin_end(18)
        top_ctrl.set_margin_top(4)

        wifi_title = Gtk.Label(label="<b>Wireless Radio</b>")
        wifi_title.set_use_markup(True)
        top_ctrl.pack_start(wifi_title, False, False, 0)

        self.wifi_power_switch = Gtk.Switch()
        self.wifi_power_switch.set_active(self.wifi_backend.is_wifi_enabled())
        self.wifi_power_switch.connect('state-set', self.on_wifi_power_toggled)
        top_ctrl.pack_start(self.wifi_power_switch, False, False, 0)

        self.wifi_scan_btn = Gtk.Button(label="Scan Networks")
        self.wifi_scan_btn.get_style_context().add_class('btn-secondary')
        self.wifi_scan_btn.connect('clicked', lambda _: self.refresh_wifi(rescan=True))
        top_ctrl.pack_end(self.wifi_scan_btn, False, False, 0)

        vbox.pack_start(top_ctrl, False, False, 0)

        # Connected Card
        self.wifi_conn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.wifi_conn_card.get_style_context().add_class('card-box-accent')

        card_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wifi_active_ssid_lbl = Gtk.Label(label="Checking connection...")
        self.wifi_active_ssid_lbl.get_style_context().add_class('card-title')
        self.wifi_active_ssid_lbl.set_halign(Gtk.Align.START)
        card_head.pack_start(self.wifi_active_ssid_lbl, True, True, 0)

        self.wifi_active_bars = SignalBarsWidget(0, width=30, height=20)
        card_head.pack_start(self.wifi_active_bars, False, False, 0)

        self.wifi_active_sig_pct = Gtk.Label(label="0%")
        self.wifi_active_sig_pct.get_style_context().add_class('pill-badge')
        self.wifi_active_sig_pct.get_style_context().add_class('badge-connected')
        card_head.pack_start(self.wifi_active_sig_pct, False, False, 0)
        self.wifi_conn_card.pack_start(card_head, False, False, 0)

        # Speed and Stats Row
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        
        # Download
        d_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        d_title = Gtk.Label(label="Download Speed")
        d_title.get_style_context().add_class('card-subtitle')
        d_title.set_halign(Gtk.Align.START)
        self.wifi_rx_lbl = Gtk.Label(label="↓ 0.0 KB/s")
        self.wifi_rx_lbl.get_style_context().add_class('speed-tag')
        self.wifi_rx_lbl.set_halign(Gtk.Align.START)
        d_box.pack_start(d_title, False, False, 0)
        d_box.pack_start(self.wifi_rx_lbl, False, False, 0)
        stats_box.pack_start(d_box, True, True, 0)

        # Upload
        u_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        u_title = Gtk.Label(label="Upload Speed")
        u_title.get_style_context().add_class('card-subtitle')
        u_title.set_halign(Gtk.Align.START)
        self.wifi_tx_lbl = Gtk.Label(label="↑ 0.0 KB/s")
        self.wifi_tx_lbl.get_style_context().add_class('speed-tag')
        self.wifi_tx_lbl.set_halign(Gtk.Align.START)
        u_box.pack_start(u_title, False, False, 0)
        u_box.pack_start(self.wifi_tx_lbl, False, False, 0)
        stats_box.pack_start(u_box, True, True, 0)

        # Link Bitrate
        r_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        r_title = Gtk.Label(label="Link Speed")
        r_title.get_style_context().add_class('card-subtitle')
        r_title.set_halign(Gtk.Align.START)
        self.wifi_bitrate_lbl = Gtk.Label(label="⚡ 0 Mbit/s")
        self.wifi_bitrate_lbl.get_style_context().add_class('speed-tag')
        self.wifi_bitrate_lbl.set_halign(Gtk.Align.START)
        r_box.pack_start(r_title, False, False, 0)
        r_box.pack_start(self.wifi_bitrate_lbl, False, False, 0)
        stats_box.pack_start(r_box, True, True, 0)

        self.wifi_conn_card.pack_start(stats_box, False, False, 0)

        # Network IP & Disconnect button
        ip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wifi_ip_details_lbl = Gtk.Label(label="IP: N/A")
        self.wifi_ip_details_lbl.get_style_context().add_class('card-subtitle')
        self.wifi_ip_details_lbl.set_halign(Gtk.Align.START)
        ip_row.pack_start(self.wifi_ip_details_lbl, True, True, 0)

        self.wifi_disc_btn = Gtk.Button(label="Disconnect")
        self.wifi_disc_btn.get_style_context().add_class('btn-danger')
        self.wifi_disc_btn.connect('clicked', self.on_wifi_disconnect_clicked)
        ip_row.pack_start(self.wifi_disc_btn, False, False, 0)
        self.wifi_conn_card.pack_start(ip_row, False, False, 0)

        vbox.pack_start(self.wifi_conn_card, False, False, 0)

        # Available Networks Section Header
        sec_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sec_header.set_margin_start(18)
        sec_header.set_margin_end(18)
        sec_title = Gtk.Label(label="<b>Available Wi-Fi Networks</b>")
        sec_title.set_use_markup(True)
        sec_header.pack_start(sec_title, True, True, 0)

        self.wifi_search_entry = Gtk.SearchEntry()
        self.wifi_search_entry.set_placeholder_text("Filter networks...")
        self.wifi_search_entry.connect('search-changed', lambda _: self.wifi_listbox.invalidate_filter())
        sec_header.pack_start(self.wifi_search_entry, False, False, 0)
        vbox.pack_start(sec_header, False, False, 0)

        # Scrollable Networks List
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self.wifi_listbox = Gtk.ListBox()
        self.wifi_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.wifi_listbox.set_filter_func(self._filter_wifi_row)
        scrolled.add(self.wifi_listbox)
        vbox.pack_start(scrolled, True, True, 0)

        return vbox

    # ----------------------------------------------------
    # Bluetooth Tab View
    # ----------------------------------------------------
    def _build_bt_view(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Controller Card
        ctrl_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ctrl_card.get_style_context().add_class('card-box')

        ctrl_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bt_icon = Gtk.Image.new_from_icon_name("bluetooth", Gtk.IconSize.LARGE_TOOLBAR)
        ctrl_head.pack_start(bt_icon, False, False, 0)

        ctrl_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.bt_name_lbl = Gtk.Label(label="Bluetooth Controller")
        self.bt_name_lbl.get_style_context().add_class('card-title')
        self.bt_name_lbl.set_halign(Gtk.Align.START)
        self.bt_mac_lbl = Gtk.Label(label="MAC: N/A")
        self.bt_mac_lbl.get_style_context().add_class('card-subtitle')
        self.bt_mac_lbl.set_halign(Gtk.Align.START)
        ctrl_info.pack_start(self.bt_name_lbl, False, False, 0)
        ctrl_info.pack_start(self.bt_mac_lbl, False, False, 0)
        ctrl_head.pack_start(ctrl_info, True, True, 0)

        # Power switch
        self.bt_power_switch = Gtk.Switch()
        self.bt_power_switch.connect('state-set', self.on_bt_power_toggled)
        ctrl_head.pack_start(self.bt_power_switch, False, False, 0)

        ctrl_card.pack_start(ctrl_head, False, False, 0)

        # Action bar in card: Scan button & status
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.bt_scan_btn = Gtk.Button(label="🔍 Scan for Nearby Devices")
        self.bt_scan_btn.get_style_context().add_class('btn-primary')
        self.bt_scan_btn.connect('clicked', self.on_bt_scan_clicked)
        action_bar.pack_start(self.bt_scan_btn, False, False, 0)

        self.bt_scan_spinner = Gtk.Spinner()
        action_bar.pack_start(self.bt_scan_spinner, False, False, 0)

        self.bt_status_lbl = Gtk.Label(label="Bluetooth Ready")
        self.bt_status_lbl.get_style_context().add_class('item-detail')
        action_bar.pack_start(self.bt_status_lbl, True, True, 0)

        ctrl_card.pack_start(action_bar, False, False, 0)
        vbox.pack_start(ctrl_card, False, False, 0)

        # Paired & Discovered Lists Container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        bt_lists_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Paired devices header
        paired_header = Gtk.Label(label="<b>Paired Devices</b>")
        paired_header.set_use_markup(True)
        paired_header.set_halign(Gtk.Align.START)
        paired_header.set_margin_start(18)
        bt_lists_box.pack_start(paired_header, False, False, 0)

        self.bt_paired_listbox = Gtk.ListBox()
        self.bt_paired_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        bt_lists_box.pack_start(self.bt_paired_listbox, False, False, 0)

        # Nearby discovered devices header
        nearby_header = Gtk.Label(label="<b>Nearby Available Devices</b>")
        nearby_header.set_use_markup(True)
        nearby_header.set_halign(Gtk.Align.START)
        nearby_header.set_margin_start(18)
        bt_lists_box.pack_start(nearby_header, False, False, 0)

        self.bt_nearby_listbox = Gtk.ListBox()
        self.bt_nearby_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        bt_lists_box.pack_start(self.bt_nearby_listbox, False, False, 0)

        scrolled.add(bt_lists_box)
        vbox.pack_start(scrolled, True, True, 0)

        return vbox

    # ----------------------------------------------------
    # Tab Switching
    # ----------------------------------------------------
    def switch_tab(self, tab_name: str):
        self.current_tab = tab_name
        self.stack.set_visible_child_name(tab_name)
        if tab_name == "wifi":
            self.tab_wifi_btn.get_style_context().add_class('active')
            self.tab_bt_btn.get_style_context().remove_class('active')
        else:
            self.tab_bt_btn.get_style_context().add_class('active')
            self.tab_wifi_btn.get_style_context().remove_class('active')

    # ----------------------------------------------------
    # Speed & Periodic Timer
    # ----------------------------------------------------
    def start_live_timer(self):
        if self.speed_timer_id is None:
            self.speed_timer_id = GLib.timeout_add_seconds(1, self.update_live_speed)

    def stop_live_timer(self):
        if self.speed_timer_id:
            GLib.source_remove(self.speed_timer_id)
            self.speed_timer_id = None

    def update_live_speed(self):
        speed_data = self.wifi_backend.get_live_speed()
        rx_fmt = speed_data['rx_fmt']
        tx_fmt = speed_data['tx_fmt']

        self.wifi_rx_lbl.set_text(f"↓ {rx_fmt}")
        self.wifi_tx_lbl.set_text(f"↑ {tx_fmt}")

        rate = self.wifi_details.get('rate', '0 Mbit/s') if self.wifi_details else "0 Mbit/s"
        self.header_speed_lbl.set_text(f"{rate} (↓ {rx_fmt})")

        # Also show speed indicated directly on the option tab itself
        if self.wifi_details and rate and rate != '0 Mbit/s':
            self.tab_wifi_btn.set_label(f"📶  Wi-Fi Networks (⚡ {rate})")
        else:
            self.tab_wifi_btn.set_label("📶  Wi-Fi Networks")

        # Update companion top header speed pill (shown only while app is open)
        if hasattr(self, 'header_pill') and self.header_pill:
            speed_text = f"⚡ {rate} (↓ {rx_fmt})" if self.wifi_details else "Wi-Fi Offline"
            self.header_pill.update_display(speed_text, bool(self.wifi_details))

        return True

    # ----------------------------------------------------
    # Global Refresh
    # ----------------------------------------------------
    def on_global_refresh_clicked(self, *args):
        if self.current_tab == "wifi":
            self.refresh_wifi(rescan=True)
        else:
            self.refresh_bluetooth()

    # ----------------------------------------------------
    # Wi-Fi Logic
    # ----------------------------------------------------
    def on_wifi_power_toggled(self, switch, state):
        def worker():
            success, msg = self.wifi_backend.set_wifi_enabled(state)
            GLib.idle_add(self._on_wifi_power_done, success, msg, state)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def _on_wifi_power_done(self, success, msg, state):
        self.status_bar.set_text(msg)
        self.refresh_wifi(rescan=False)

    def refresh_wifi(self, rescan: bool = False):
        if self.is_wifi_scanning:
            return
        self.is_wifi_scanning = True
        self.refresh_spinner.start()
        self.status_bar.set_text("Scanning for Wi-Fi networks...")

        def worker():
            details = self.wifi_backend.get_connected_details()
            nets = self.wifi_backend.scan_networks(rescan=rescan)
            GLib.idle_add(self._on_wifi_scan_complete, details, nets)

        threading.Thread(target=worker, daemon=True).start()

    def _on_wifi_scan_complete(self, details, nets):
        self.is_wifi_scanning = False
        self.refresh_spinner.stop()
        self.status_bar.set_text(f"Wi-Fi: {len(nets)} networks found")
        self.wifi_details = details
        self.wifi_networks = nets

        # Update Connected Card
        if details:
            self.wifi_active_ssid_lbl.set_text(f"Connected: {details.get('ssid')}")
            sig = details.get('signal', 0)
            self.wifi_active_bars.set_signal(sig)
            self.wifi_active_sig_pct.set_text(f"{sig}%")
            self.wifi_bitrate_lbl.set_text(f"⚡ {details.get('rate', 'N/A')}")
            self.wifi_ip_details_lbl.set_text(f"IP: {details.get('ip4')} • Gateway: {details.get('gateway')} • DNS: {details.get('dns')}")
            self.wifi_disc_btn.set_visible(True)
        else:
            self.wifi_active_ssid_lbl.set_text("Not Connected to Wi-Fi")
            self.wifi_active_bars.set_signal(0)
            self.wifi_active_sig_pct.set_text("Offline")
            self.wifi_bitrate_lbl.set_text("⚡ 0 Mbit/s")
            self.wifi_ip_details_lbl.set_text("Select an available network below to connect")
            self.wifi_disc_btn.set_visible(False)

        # Clear and repopulate listbox
        for child in self.wifi_listbox.get_children():
            self.wifi_listbox.remove(child)

        for net in nets:
            row_w = NetworkRowWidget(
                net,
                on_connect_cb=self.on_wifi_connect_request,
                on_disconnect_cb=self.on_wifi_disconnect_clicked
            )
            row = Gtk.ListBoxRow()
            row.add(row_w)
            row.net_info = net
            self.wifi_listbox.add(row)

        self.wifi_listbox.show_all()

    def _filter_wifi_row(self, row):
        query = self.wifi_search_entry.get_text().strip().lower()
        if not query:
            return True
        ssid = row.net_info.get('ssid', '').lower()
        bssid = row.net_info.get('bssid', '').lower()
        return query in ssid or query in bssid

    def on_wifi_connect_request(self, net_info: dict):
        ssid = net_info.get('ssid')
        is_secured = net_info.get('is_secured', False)
        is_saved = net_info.get('is_saved', False)

        if is_saved or not is_secured:
            self._execute_wifi_connect(ssid, password=None)
        else:
            dlg = PasswordDialog(self, ssid)
            resp = dlg.run()
            pwd = dlg.get_password()
            dlg.destroy()
            if resp == Gtk.ResponseType.OK:
                if not pwd:
                    self.status_bar.set_text("Password cannot be empty.")
                    return
                self._execute_wifi_connect(ssid, password=pwd)

    def _execute_wifi_connect(self, ssid: str, password=None):
        self.status_bar.set_text(f"Connecting to '{ssid}'...")
        self.refresh_spinner.start()

        def worker():
            success, msg = self.wifi_backend.connect_network(ssid, password=password)
            GLib.idle_add(self._on_wifi_connect_done, success, msg, ssid)

        threading.Thread(target=worker, daemon=True).start()

    def _on_wifi_connect_done(self, success, msg, ssid):
        self.refresh_spinner.stop()
        if success:
            self.status_bar.set_text(f"Connected to '{ssid}' successfully!")
            self.refresh_wifi(rescan=False)
        else:
            self.status_bar.set_text(f"Connection error: {msg}")

    def on_wifi_disconnect_clicked(self, *args):
        self.status_bar.set_text("Disconnecting Wi-Fi...")
        def worker():
            success, msg = self.wifi_backend.disconnect_network()
            GLib.idle_add(self._on_wifi_disconnect_done, success, msg)
        threading.Thread(target=worker, daemon=True).start()

    def _on_wifi_disconnect_done(self, success, msg):
        self.status_bar.set_text(msg)
        self.refresh_wifi(rescan=False)

    # ----------------------------------------------------
    # Bluetooth Logic
    # ----------------------------------------------------
    def on_bt_power_toggled(self, switch, state):
        def worker():
            success, msg = self.bt_backend.set_powered(state)
            GLib.idle_add(self._on_bt_power_done, success, msg)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def _on_bt_power_done(self, success, msg):
        self.status_bar.set_text(msg)
        self.refresh_bluetooth()

    def refresh_bluetooth(self):
        def worker():
            ctrl = self.bt_backend.get_controller_status()
            paired, nearby = self.bt_backend.get_all_devices()
            GLib.idle_add(self._on_bt_data_loaded, ctrl, paired, nearby)
        threading.Thread(target=worker, daemon=True).start()

    def _on_bt_data_loaded(self, ctrl, paired, nearby):
        self.bt_name_lbl.set_text(ctrl.get('name', 'Bluetooth Controller'))
        self.bt_mac_lbl.set_text(f"MAC: {ctrl.get('mac', 'N/A')}")
        self.bt_power_switch.set_active(ctrl.get('powered', False))
        self.bt_status_lbl.set_text("Powered ON" if ctrl.get('powered') else "Powered OFF")

        self.bt_paired = paired
        self.bt_nearby = nearby

        # Paired list
        for child in self.bt_paired_listbox.get_children():
            self.bt_paired_listbox.remove(child)

        if not paired:
            empty_lbl = Gtk.Label(label="No paired Bluetooth devices.")
            empty_lbl.get_style_context().add_class('item-detail')
            empty_lbl.set_halign(Gtk.Align.START)
            empty_lbl.set_margin_start(20)
            self.bt_paired_listbox.add(empty_lbl)
        else:
            for dev in paired:
                row_w = BluetoothRowWidget(
                    dev,
                    on_connect_cb=self.on_bt_connect_device,
                    on_disconnect_cb=self.on_bt_disconnect_device,
                    on_remove_cb=self.on_bt_remove_device
                )
                self.bt_paired_listbox.add(row_w)

        # Nearby list
        for child in self.bt_nearby_listbox.get_children():
            self.bt_nearby_listbox.remove(child)

        if not nearby:
            empty_lbl = Gtk.Label(label="Click 'Scan for Nearby Devices' to discover accessories.")
            empty_lbl.get_style_context().add_class('item-detail')
            empty_lbl.set_halign(Gtk.Align.START)
            empty_lbl.set_margin_start(20)
            self.bt_nearby_listbox.add(empty_lbl)
        else:
            for dev in nearby:
                row_w = BluetoothRowWidget(
                    dev,
                    on_connect_cb=self.on_bt_connect_device,
                    on_disconnect_cb=self.on_bt_disconnect_device
                )
                self.bt_nearby_listbox.add(row_w)

        self.bt_paired_listbox.show_all()
        self.bt_nearby_listbox.show_all()

    def on_bt_scan_clicked(self, *args):
        if self.is_bt_scanning:
            return
        self.is_bt_scanning = True
        self.bt_scan_btn.set_sensitive(False)
        self.bt_scan_spinner.start()
        self.bt_status_lbl.set_text("Scanning for devices (6s)...")

        def worker():
            self.bt_backend.scan_for_devices(timeout_sec=6)
            GLib.idle_add(self._on_bt_scan_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _on_bt_scan_finished(self):
        self.is_bt_scanning = False
        self.bt_scan_btn.set_sensitive(True)
        self.bt_scan_spinner.stop()
        self.bt_status_lbl.set_text("Scan finished.")
        self.refresh_bluetooth()

    def on_bt_connect_device(self, mac: str, is_paired: bool):
        self.status_bar.set_text(f"Connecting to {mac}...")
        def worker():
            if not is_paired:
                self.bt_backend.pair_device(mac)
            success, msg = self.bt_backend.connect_device(mac)
            GLib.idle_add(self._on_bt_action_done, msg)
        threading.Thread(target=worker, daemon=True).start()

    def on_bt_disconnect_device(self, mac: str):
        self.status_bar.set_text(f"Disconnecting {mac}...")
        def worker():
            success, msg = self.bt_backend.disconnect_device(mac)
            GLib.idle_add(self._on_bt_action_done, msg)
        threading.Thread(target=worker, daemon=True).start()

    def on_bt_remove_device(self, mac: str):
        self.status_bar.set_text(f"Removing {mac}...")
        def worker():
            success, msg = self.bt_backend.remove_device(mac)
            GLib.idle_add(self._on_bt_action_done, msg)
        threading.Thread(target=worker, daemon=True).start()

    def _on_bt_action_done(self, msg: str):
        self.status_bar.set_text(msg)
        self.refresh_bluetooth()

    def on_destroy(self, *args):
        self.stop_live_timer()
        if hasattr(self, 'header_pill') and self.header_pill:
            try:
                self.header_pill.destroy()
            except Exception:
                pass
            self.header_pill = None
        Gtk.main_quit()
