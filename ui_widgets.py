"""
Custom UI widgets for Network & Bluetooth Manager:
- SignalBarsWidget: Crisp Cairo-drawn 4-bar signal strength indicator
- NetworkRowWidget: Wi-Fi card row with connect action
- BluetoothRowWidget: Bluetooth card row with pair/connect/forget actions
- PasswordDialog: Password prompt modal with reveal toggle
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from typing import Callable, Optional, Dict


class SignalBarsWidget(Gtk.DrawingArea):
    """
    Renders 4 modern vertical rounded signal bars with dynamic color based on signal percentage.
    """
    def __init__(self, signal_percent: int = 0, width: int = 28, height: int = 20):
        super().__init__()
        self.signal_percent = max(0, min(100, signal_percent))
        self.set_size_request(width, height)
        self.connect('draw', self.on_draw)

    def set_signal(self, percent: int):
        self.signal_percent = max(0, min(100, percent))
        self.queue_draw()

    def on_draw(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Calculate number of active bars
        if self.signal_percent <= 0:
            active_bars = 0
            color = (0.5, 0.5, 0.5)  # gray
        elif self.signal_percent < 30:
            active_bars = 1
            color = (0.94, 0.27, 0.27)  # red
        elif self.signal_percent < 55:
            active_bars = 2
            color = (0.96, 0.62, 0.04)  # amber
        elif self.signal_percent < 80:
            active_bars = 3
            color = (0.52, 0.80, 0.08)  # lime
        else:
            active_bars = 4
            color = (0.06, 0.73, 0.51)  # bright green

        dim_color = (0.2, 0.25, 0.35)

        num_bars = 4
        bar_gap = 2.5
        total_gaps = (num_bars - 1) * bar_gap
        bar_w = (width - total_gaps) / num_bars

        # Draw 4 bars with heights 30%, 52%, 76%, 100%
        height_fractions = [0.32, 0.54, 0.77, 1.0]

        for i in range(num_bars):
            bar_h = height * height_fractions[i]
            x = i * (bar_w + bar_gap)
            y = height - bar_h

            if i < active_bars:
                cr.set_source_rgb(*color)
            else:
                cr.set_source_rgb(*dim_color)

            # Draw rounded rectangle for bar
            radius = min(bar_w / 2, 2.5)
            self._rounded_rect(cr, x, y, bar_w, bar_h, radius)
            cr.fill()

        return False

    def _rounded_rect(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.57, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.57)
        cr.arc(x + r, y + h - r, r, 1.57, 3.14)
        cr.arc(x + r, y + r, r, 3.14, 4.71)
        cr.close_path()


class NetworkRowWidget(Gtk.Box):
    """
    Card widget representing an individual Wi-Fi network in the list.
    """
    def __init__(self, net_info: Dict, on_connect_cb: Callable, on_disconnect_cb: Optional[Callable] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.net_info = net_info
        self.on_connect_cb = on_connect_cb
        self.on_disconnect_cb = on_disconnect_cb

        in_use = net_info.get('in_use', False)
        if in_use:
            self.get_style_context().add_class('item-row-active')
        else:
            self.get_style_context().add_class('item-row')

        # Left: Signal strength indicator
        signal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        signal_box.set_valign(Gtk.Align.CENTER)
        bars = SignalBarsWidget(net_info.get('signal', 0), width=26, height=18)
        sig_lbl = Gtk.Label(label=f"{net_info.get('signal', 0)}%")
        sig_lbl.get_style_context().add_class('item-detail')
        signal_box.pack_start(bars, False, False, 0)
        signal_box.pack_start(sig_lbl, False, False, 0)
        self.pack_start(signal_box, False, False, 0)

        # Middle: SSID and metadata
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info_box.set_valign(Gtk.Align.CENTER)
        info_box.set_hexpand(True)

        top_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ssid_lbl = Gtk.Label(label=net_info.get('ssid', 'Unknown'))
        ssid_lbl.get_style_context().add_class('item-title')
        ssid_lbl.set_halign(Gtk.Align.START)
        ssid_lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        top_line.pack_start(ssid_lbl, False, False, 0)

        # Security pill
        sec = net_info.get('security', 'Open')
        if sec and sec != 'Open' and sec != '--':
            sec_badge = Gtk.Label(label=f"🔒 {sec}")
            sec_badge.get_style_context().add_class('pill-badge')
            sec_badge.get_style_context().add_class('badge-secure')
            top_line.pack_start(sec_badge, False, False, 0)
        else:
            sec_badge = Gtk.Label(label="🔓 Open")
            sec_badge.get_style_context().add_class('pill-badge')
            sec_badge.get_style_context().add_class('badge-open')
            top_line.pack_start(sec_badge, False, False, 0)

        # Speed indicator badge on this existing option
        rate = net_info.get('rate', '')
        if rate and rate != 'N/A':
            speed_badge = Gtk.Label(label=f"⚡ {rate}")
            speed_badge.get_style_context().add_class('pill-badge')
            speed_badge.get_style_context().add_class('badge-speed')
            top_line.pack_start(speed_badge, False, False, 0)

        if net_info.get('is_saved', False) and not in_use:
            saved_badge = Gtk.Label(label="Saved")
            saved_badge.get_style_context().add_class('pill-badge')
            saved_badge.get_style_context().add_class('badge-saved')
            top_line.pack_start(saved_badge, False, False, 0)

        info_box.pack_start(top_line, False, False, 0)

        # Subtitle: Channel, Rate, BSSID
        chan = net_info.get('channel', 'auto')
        rate = net_info.get('rate', 'N/A')
        bssid = net_info.get('bssid', '')
        sub_text = f"Channel {chan} • Max {rate}"
        if bssid:
            sub_text += f" • {bssid}"
        sub_lbl = Gtk.Label(label=sub_text)
        sub_lbl.get_style_context().add_class('item-detail')
        sub_lbl.set_halign(Gtk.Align.START)
        info_box.pack_start(sub_lbl, False, False, 0)

        self.pack_start(info_box, True, True, 0)

        # Right: Action button
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_box.set_valign(Gtk.Align.CENTER)

        if in_use:
            conn_badge = Gtk.Label(label="✓ Connected")
            conn_badge.get_style_context().add_class('pill-badge')
            conn_badge.get_style_context().add_class('badge-connected')
            action_box.pack_start(conn_badge, False, False, 0)

            if on_disconnect_cb:
                disc_btn = Gtk.Button(label="Disconnect")
                disc_btn.get_style_context().add_class('btn-danger')
                disc_btn.connect('clicked', lambda _: on_disconnect_cb())
                action_box.pack_start(disc_btn, False, False, 0)
        else:
            conn_btn = Gtk.Button(label="Connect")
            conn_btn.get_style_context().add_class('btn-connect')
            conn_btn.connect('clicked', lambda _: on_connect_cb(self.net_info))
            action_box.pack_start(conn_btn, False, False, 0)

        self.pack_start(action_box, False, False, 0)


class BluetoothRowWidget(Gtk.Box):
    """
    Card widget representing an individual Bluetooth device.
    """
    def __init__(self, dev_info: Dict, on_connect_cb: Callable, on_disconnect_cb: Callable, on_remove_cb: Optional[Callable] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.dev_info = dev_info
        self.get_style_context().add_class('item-row')

        # Icon mapping
        icon_name = "bluetooth"
        raw_icon = dev_info.get('raw_icon', '')
        dev_type = dev_info.get('icon', '')
        if dev_type == 'headset' or 'audio' in raw_icon:
            icon_name = "audio-headphones"
        elif dev_type == 'phone':
            icon_name = "phone"
        elif dev_type == 'keyboard':
            icon_name = "input-keyboard"
        elif dev_type == 'mouse':
            icon_name = "input-mouse"

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        icon.set_valign(Gtk.Align.CENTER)
        self.pack_start(icon, False, False, 0)

        # Details
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_valign(Gtk.Align.CENTER)
        info_box.set_hexpand(True)

        top_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_lbl = Gtk.Label(label=dev_info.get('name', 'Unknown Device'))
        name_lbl.get_style_context().add_class('item-title')
        name_lbl.set_halign(Gtk.Align.START)
        top_line.pack_start(name_lbl, False, False, 0)

        if dev_info.get('connected', False):
            badge = Gtk.Label(label="Connected")
            badge.get_style_context().add_class('pill-badge')
            badge.get_style_context().add_class('badge-connected')
            top_line.pack_start(badge, False, False, 0)
        elif dev_info.get('paired', False):
            badge = Gtk.Label(label="Paired")
            badge.get_style_context().add_class('pill-badge')
            badge.get_style_context().add_class('badge-saved')
            top_line.pack_start(badge, False, False, 0)

        info_box.pack_start(top_line, False, False, 0)

        mac_lbl = Gtk.Label(label=dev_info.get('mac', ''))
        mac_lbl.get_style_context().add_class('item-detail')
        mac_lbl.set_halign(Gtk.Align.START)
        info_box.pack_start(mac_lbl, False, False, 0)

        self.pack_start(info_box, True, True, 0)

        # Action Buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_box.set_valign(Gtk.Align.CENTER)

        if dev_info.get('connected', False):
            disc_btn = Gtk.Button(label="Disconnect")
            disc_btn.get_style_context().add_class('btn-danger')
            disc_btn.connect('clicked', lambda _: on_disconnect_cb(dev_info['mac']))
            action_box.pack_start(disc_btn, False, False, 0)
        else:
            conn_btn = Gtk.Button(label="Connect" if dev_info.get('paired') else "Pair & Connect")
            conn_btn.get_style_context().add_class('btn-connect')
            conn_btn.connect('clicked', lambda _: on_connect_cb(dev_info['mac'], dev_info.get('paired', False)))
            action_box.pack_start(conn_btn, False, False, 0)

        if dev_info.get('paired', False) and on_remove_cb:
            unpair_btn = Gtk.Button(label="Forget")
            unpair_btn.get_style_context().add_class('btn-secondary')
            unpair_btn.connect('clicked', lambda _: on_remove_cb(dev_info['mac']))
            action_box.pack_start(unpair_btn, False, False, 0)

        self.pack_start(action_box, False, False, 0)


class PasswordDialog(Gtk.Dialog):
    """
    Modal dialog prompting user for Wi-Fi password with eye icon toggle.
    """
    def __init__(self, parent_window: Gtk.Window, ssid: str):
        super().__init__(
            title=f"Connect to {ssid}",
            transient_for=parent_window,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        self.set_default_size(380, 200)
        self.set_border_width(16)
        self.set_resizable(False)

        box = self.get_content_area()
        box.set_spacing(12)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lock_icon = Gtk.Image.new_from_icon_name("network-wireless-encrypted", Gtk.IconSize.DIALOG)
        header.pack_start(lock_icon, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        escaped_ssid = GLib.markup_escape_text(ssid)
        title_lbl = Gtk.Label(label=f"<b>Enter Password for '{escaped_ssid}'</b>")
        title_lbl.set_use_markup(True)
        title_lbl.set_halign(Gtk.Align.START)
        desc_lbl = Gtk.Label(label="This network requires WPA/WPA2 authentication.")
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.get_style_context().add_class('item-detail')
        text_box.pack_start(title_lbl, False, False, 0)
        text_box.pack_start(desc_lbl, False, False, 0)
        header.pack_start(text_box, True, True, 0)
        box.pack_start(header, False, False, 0)

        # Password input box with reveal eye
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Wi-Fi Password")
        self.entry.set_hexpand(True)
        self.entry.connect('activate', lambda _: self.response(Gtk.ResponseType.OK))

        eye_btn = Gtk.Button()
        eye_img = Gtk.Image.new_from_icon_name("view-reveal-symbolic", Gtk.IconSize.BUTTON)
        eye_btn.set_image(eye_img)
        eye_btn.set_tooltip_text("Show password")

        def toggle_reveal(btn):
            visible = not self.entry.get_visibility()
            self.entry.set_visibility(visible)
            icon = "view-conceal-symbolic" if visible else "view-reveal-symbolic"
            eye_img.set_from_icon_name(icon, Gtk.IconSize.BUTTON)

        eye_btn.connect('clicked', toggle_reveal)
        entry_box.pack_start(self.entry, True, True, 0)
        entry_box.pack_start(eye_btn, False, False, 0)
        box.pack_start(entry_box, False, False, 0)

        # Buttons
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        connect_btn = self.add_button("Connect", Gtk.ResponseType.OK)
        connect_btn.get_style_context().add_class('btn-primary')
        self.set_default_response(Gtk.ResponseType.OK)

        self.show_all()

    def get_password(self) -> str:
        return self.entry.get_text().strip()
