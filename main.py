#!/usr/bin/env python3
"""
Wi-Fi and Bluetooth Manager for Linux Debian.
Command-line Entry Point.
"""

import sys
import os
import argparse
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from backend import WiFiBackend, BluetoothBackend
from ui_style import apply_app_styles
from app_window import MainWindow
from quick_dialog import QuickWiFiDialog
from speed_indicator import SpeedIndicatorService


def main():
    parser = argparse.ArgumentParser(description="Linux Debian Wi-Fi & Bluetooth UI Manager")
    parser.add_argument('--indicator', action='store_true', help="Run top-right speed indicator service")
    parser.add_argument('--quick-dialog', action='store_true', help="Open the Quick Wi-Fi switch dialog directly")
    parser.add_argument('--no-floating', action='store_true', help="Disable the top-right screen floating button")
    args = parser.parse_args()

    apply_app_styles()

    wifi_backend = WiFiBackend()
    bt_backend = BluetoothBackend()

    if args.indicator:
        # Run top-right speed indicator service
        service = SpeedIndicatorService(enable_floating=not args.no_floating)
        Gtk.main()
    elif args.quick_dialog:
        # Run quick dialog directly
        dlg = QuickWiFiDialog(wifi_backend)
        dlg.connect('destroy', Gtk.main_quit)
        dlg.show_all()
        Gtk.main()
    else:
        # Launch Main Control Center Window (speed is shown only while app is open)
        win = MainWindow(wifi_backend, bt_backend)
        win.connect('destroy', Gtk.main_quit)
        win.show_all()
        win.present()
        Gtk.main()


if __name__ == '__main__':
    main()
