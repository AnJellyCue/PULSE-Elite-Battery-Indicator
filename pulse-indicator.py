#!/usr/bin/env python3

import subprocess
import time
import glob
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import Gtk, GLib, Pango, AyatanaAppIndicator3


BATTERY_CMD = "/usr/local/bin/pulse-battery"
ADAPTER_ID = "054c:0ecc"

last_battery = None
last_update = None
last_response_ms = None
successful_reads = 0
failed_reads = 0


indicator = AyatanaAppIndicator3.Indicator.new(
    "pulse-elite",
    "audio-headphones",
    AyatanaAppIndicator3.IndicatorCategory.HARDWARE,
)

indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title("PULSE Elite")


def get_battery():
    global last_response_ms
    global successful_reads
    global failed_reads

    start = time.monotonic()

    try:
        output = subprocess.check_output(
            [BATTERY_CMD],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )

        last_response_ms = round((time.monotonic() - start) * 1000, 1)

        for line in output.splitlines():
            if "%" in line:
                value = int(line.split("%")[0].split()[-1])
                successful_reads += 1
                return value

        failed_reads += 1

    except Exception:
        failed_reads += 1

    return None


def adapter_present():
    try:
        result = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return ADAPTER_ID.lower() in result.stdout.lower()
    except Exception:
        return False


def hid_devices():
    devices = []

    for device in glob.glob("/dev/hidraw*"):
        try:
            result = subprocess.run(
                ["udevadm", "info", "--query=property", "--name", device],
                capture_output=True,
                text=True,
                timeout=2,
            )

            data = result.stdout.upper()

            if "054C" in data and "0ECC" in data:
                devices.append(device)

        except Exception:
            pass

    return devices


def connection_status():
    if not adapter_present():
        return "🔴 Not detected"

    if not hid_devices():
        return "🟠 HID unavailable"

    if last_battery is None:
        return "🟠 Not responding"

    return "🟢 Connected"


def health_status():
    if last_battery is None:
        return "🔴 Problem"

    if last_response_ms is not None and last_response_ms < 100:
        return "🟢 Excellent"

    if last_response_ms is not None and last_response_ms < 500:
        return "🟢 Good"

    return "🟠 Slow"


def update():
    global last_battery
    global last_update

    battery = get_battery()

    if battery is None:
        last_battery = None
        indicator.set_label("🔋 --%", "")
    else:
        last_battery = battery
        last_update = time.time()
        indicator.set_label(f"🔋 {battery}%", "")

    update_menu()

    return True


def set_value(label, value):
    label.set_text(value)


def make_row(icon, name, value):
    row = Gtk.MenuItem(label="")
    label = row.get_child()
    label.set_xalign(0)

    font = Pango.FontDescription("monospace 10")
    label.override_font(font)

    return row, label


def update_menu():
    # Calibrated spacing compensates for the different widths of emoji glyphs.

    battery_value.set_text(
        f"🔋  Battery                  "
        f"{'--' if last_battery is None else f'{last_battery}%'}"
    )

    connection_value.set_text(
        f"🔌 Connection            "
        "● Connected"
    )

    health_value.set_text(
        f"🩺 Health                    "
        "● Excellent"
    )

    response_value.set_text(
        f"⚡ Response                "
        f"{'--' if last_response_ms is None else f'{last_response_ms} ms'}"
    )

    if last_update is None:
        age_text = "--"
    else:
        age_text = f"{int(time.time() - last_update)}s ago"

    update_value.set_text(
        f"⏱️ Last update             "
        f"{age_text}"
    )

def run_diagnostics(_item):
    adapter = adapter_present()
    devices = hid_devices()

    adapter_result = "🟢 OK" if adapter else "🔴 NOT FOUND"
    hid_result = (
        f"🟢 {devices[0]}"
        if devices else "🔴 NOT FOUND"
    )

    battery_result = (
        f"🟢 {last_battery}%"
        if last_battery is not None
        else "🔴 FAILED"
    )

    response_result = (
        f"🟢 {last_response_ms} ms"
        if last_response_ms is not None
        else "🔴 FAILED"
    )

    overall = (
        "🟢 HEALTHY"
        if last_battery is not None and adapter and devices
        else "🟠 PARTIAL"
        if adapter
        else "🔴 PROBLEM"
    )

    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="🎧 PULSE Elite Diagnostics",
    )

    dialog.format_secondary_text(
        f"""
PlayStation Link    {adapter_result}
HID interface       {hid_result}
Battery report      {battery_result}
HID response        {response_result}

Successful reads    {successful_reads}
Failed reads        {failed_reads}

Overall health      {overall}
"""
    )

    dialog.run()
    dialog.destroy()


def refresh(_item):
    update()


def quit_app(_item):
    Gtk.main_quit()


# ------------------------------------------------------------
# Menu
# ------------------------------------------------------------

menu = Gtk.Menu()

title = Gtk.MenuItem(label="🎧  PULSE Elite")
title.set_sensitive(False)
menu.append(title)

menu.append(Gtk.SeparatorMenuItem())

battery_item, battery_value = make_row(
    "🔋", "Battery", "--"
)

connection_item, connection_value = make_row(
    "🔌", "Connection", "Checking…"
)

health_item, health_value = make_row(
    "🩺", "Health", "Checking…"
)

response_item, response_value = make_row(
    "⚡", "Response", "--"
)

update_item, update_value = make_row(
    "⏱️", "Last update", "--"
)

menu.append(battery_item)
menu.append(connection_item)
menu.append(health_item)
menu.append(response_item)
menu.append(update_item)

menu.append(Gtk.SeparatorMenuItem())

refresh_item = Gtk.MenuItem(label="🔄  Refresh now")
refresh_item.connect("activate", refresh)
menu.append(refresh_item)

diagnostics_item = Gtk.MenuItem(label="🩺  Run diagnostics")
diagnostics_item.connect("activate", run_diagnostics)
menu.append(diagnostics_item)

menu.append(Gtk.SeparatorMenuItem())

quit_item = Gtk.MenuItem(label="Quit")
quit_item.connect("activate", quit_app)
menu.append(quit_item)

menu.show_all()
indicator.set_menu(menu)

update()

GLib.timeout_add_seconds(60, update)

Gtk.main()
