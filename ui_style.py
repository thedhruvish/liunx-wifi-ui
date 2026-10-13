"""
Modern Dark CSS styles for GTK 3 Network & Bluetooth Manager.
"""

CSS_STYLES = b"""
/* Global Window Theme */
window.main-window {
    background-color: #0f172a;
    color: #f8fafc;
}

headerbar {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 6px 12px;
}

headerbar .title {
    font-weight: bold;
    font-size: 15px;
    color: #f8fafc;
}

headerbar .subtitle {
    font-size: 11px;
    color: #94a3b8;
}

/* Tab Switcher */
.tab-switcher {
    background-color: #1e293b;
    border-radius: 10px;
    padding: 4px;
    margin: 8px 16px;
    border: 1px solid #334155;
}

.tab-btn {
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
    background: transparent;
    border: none;
    transition: all 200ms ease;
}

.tab-btn:hover {
    color: #f8fafc;
    background-color: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
    background-color: #0284c7;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
}

/* Card Containers */
.card-box {
    background-color: #1e293b;
    border-radius: 14px;
    padding: 16px;
    margin: 8px 16px;
    border: 1px solid #334155;
}

.card-box-accent {
    background: linear-gradient(135deg, #0f2b48 0%, #1e293b 100%);
    border-radius: 14px;
    padding: 16px;
    margin: 8px 16px;
    border: 1px solid #0284c7;
    box-shadow: 0 4px 16px rgba(2, 132, 199, 0.15);
}

.card-title {
    font-size: 14px;
    font-weight: bold;
    color: #38bdf8;
    letter-spacing: 0.3px;
}

.card-subtitle {
    font-size: 11px;
    color: #94a3b8;
}

/* Network / Device Rows */
.item-row {
    background-color: #182234;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 4px 16px;
    border: 1px solid #293548;
    transition: all 150ms ease;
}

.item-row:hover {
    background-color: #222f46;
    border-color: #3b82f6;
}

.item-row-active {
    background-color: #13334c;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 4px 16px;
    border: 1px solid #0ea5e9;
}

.item-title {
    font-size: 13px;
    font-weight: 600;
    color: #f1f5f9;
}

.item-detail {
    font-size: 11px;
    color: #94a3b8;
}

/* Badges & Pills */
.pill-badge {
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

.badge-connected {
    background-color: #065f46;
    color: #34d399;
    border: 1px solid #10b981;
}

.badge-saved {
    background-color: #1e3a8a;
    color: #93c5fd;
    border: 1px solid #3b82f6;
}

.badge-secure {
    background-color: #312e81;
    color: #c7d2fe;
    border: 1px solid #6366f1;
}

.badge-open {
    background-color: #713f12;
    color: #fde047;
    border: 1px solid #eab308;
}

.badge-speed {
    background-color: #0c4a6e;
    color: #38bdf8;
    border: 1px solid #0284c7;
    font-weight: bold;
}

/* Buttons */
.btn-primary {
    background-color: #0284c7;
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
    border-radius: 8px;
    padding: 6px 14px;
    border: none;
}

.btn-primary:hover {
    background-color: #0369a1;
}

.btn-secondary {
    background-color: #334155;
    color: #f8fafc;
    font-size: 12px;
    border-radius: 8px;
    padding: 6px 12px;
    border: none;
}

.btn-secondary:hover {
    background-color: #475569;
}

.btn-danger {
    background-color: #991b1b;
    color: #fecaca;
    font-size: 12px;
    border-radius: 8px;
    padding: 6px 12px;
    border: none;
}

.btn-danger:hover {
    background-color: #b91c1c;
}

.btn-connect {
    background-color: #0284c7;
    color: #ffffff;
    font-weight: bold;
    font-size: 11px;
    border-radius: 6px;
    padding: 4px 12px;
    border: none;
}

.btn-connect:hover {
    background-color: #0ea5e9;
}

/* Speed Meter Badges */
.speed-tag {
    font-family: monospace;
    font-size: 12px;
    font-weight: bold;
    color: #38bdf8;
    background-color: #0b1e36;
    border-radius: 6px;
    padding: 3px 8px;
    border: 1px solid #0284c7;
}

/* Search and Input Fields */
entry {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}

entry:focus {
    border-color: #0ea5e9;
    box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.2);
}

/* Floating pill button */
.floating-pill {
    background-color: #0f172a;
    border: 2px solid #0284c7;
    border-radius: 20px;
    padding: 4px 14px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
}

.floating-pill:hover {
    background-color: #1e293b;
    border-color: #38bdf8;
}

/* Top Header Row Speed Pill (inside panel row next to notification icon) */
.header-speed-pill {
    background-color: rgba(30, 41, 59, 0.95);
    border: 1px solid #0284c7;
    border-radius: 6px;
}

.header-speed-btn {
    background: transparent;
    border: none;
    padding: 1px 8px;
    box-shadow: none;
}

.header-speed-btn:hover {
    background-color: rgba(2, 132, 199, 0.3);
    border-radius: 5px;
}

.header-speed-text {
    color: #38bdf8;
    font-weight: bold;
    font-size: 11px;
    font-family: monospace, Sans;
}

/* Quick Dialog */
.quick-dialog {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 14px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
}

/* Scrollbar */
scrollbar slider {
    background-color: #475569;
    border-radius: 4px;
    min-width: 6px;
}

scrollbar slider:hover {
    background-color: #64748b;
}
"""

def apply_app_styles():
    """Apply the custom modern dark CSS stylesheet to the default Gdk screen."""
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS_STYLES)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
