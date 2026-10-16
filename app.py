#!/usr/bin/env python3
"""Predator Control MVP: read-only monitoring for Acer Predator laptops on Linux."""

import glob
import os
import subprocess
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

APP_TITLE = "Predator Control"
REFRESH_MS = 2000


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, UnicodeError):
        return None


def first_existing(paths):
    for path in paths:
        value = read_text(path)
        if value is not None:
            return value
    return None


def fmt_number(value, suffix=""):
    if value is None or value == "":
        return "Not available"
    return f"{value}{suffix}"


def battery_info():
    result = {}
    batteries = sorted(glob.glob("/sys/class/power_supply/BAT*"))
    if not batteries:
        return {"Battery": "No BAT* device found"}

    # Prefer BAT1 on this machine if present; otherwise use the first battery.
    bat = next((p for p in batteries if os.path.basename(p) == "BAT1"), batteries[0])
    result["Battery device"] = os.path.basename(bat)

    capacity = read_text(os.path.join(bat, "capacity"))
    result["Charge"] = fmt_number(capacity, "%")

    status = read_text(os.path.join(bat, "status"))
    result["Status"] = status or "Not available"

    full = read_text(os.path.join(bat, "charge_full"))
    design = read_text(os.path.join(bat, "charge_full_design"))
    if full and design:
        try:
            full_i, design_i = int(full), int(design)
            if design_i > 0:
                result["Estimated health"] = f"{full_i / design_i * 100:.1f}%"
                result["Full-charge capacity"] = f"{full_i / 1_000_000:.2f} Ah"
                result["Design capacity"] = f"{design_i / 1_000_000:.2f} Ah"
            else:
                result["Estimated health"] = "Not available"
        except ValueError:
            result["Estimated health"] = "Not available"
    else:
        # Some kernels expose energy_* instead of charge_*.
        full_e = read_text(os.path.join(bat, "energy_full"))
        design_e = read_text(os.path.join(bat, "energy_full_design"))
        try:
            if full_e and design_e and int(design_e) > 0:
                result["Estimated health"] = f"{int(full_e) / int(design_e) * 100:.1f}%"
                result["Full-charge capacity"] = f"{int(full_e) / 1_000_000:.2f} Wh"
                result["Design capacity"] = f"{int(design_e) / 1_000_000:.2f} Wh"
            else:
                result["Estimated health"] = "Not exposed by kernel"
        except ValueError:
            result["Estimated health"] = "Not available"

    cycles = read_text(os.path.join(bat, "cycle_count"))
    result["Cycle count"] = cycles or "Not exposed by kernel"
    return result


def thermal_info():
    result = {}
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name = read_text(os.path.join(hwmon, "name")) or os.path.basename(hwmon)
        # Fan RPMs
        for path in sorted(glob.glob(os.path.join(hwmon, "fan*_input"))):
            key = os.path.basename(path).replace("_input", "")
            value = read_text(path)
            if value and value.isdigit():
                result[f"{name}: {key}"] = f"{int(value)} RPM"
        # Temperature inputs and their optional labels
        for path in sorted(glob.glob(os.path.join(hwmon, "temp*_input"))):
            stem = os.path.basename(path).replace("_input", "")
            value = read_text(path)
            if not value:
                continue
            try:
                celsius = int(value) / 1000.0
            except ValueError:
                continue
            label = read_text(os.path.join(hwmon, stem + "_label"))
            label = label or stem
            result[f"{name}: {label}"] = f"{celsius:.1f} °C"
    return result


def profile_info():
    current = read_text("/sys/firmware/acpi/platform_profile")
    choices = read_text("/sys/firmware/acpi/platform_profile_choices")
    return current or "Not exposed", choices or "Not exposed"


class PredatorControl(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.example.PredatorControl")
        self.window = None
        self.value_labels = {}

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self, title=APP_TITLE)
        self.window.set_default_size(680, 620)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)
        self.window.set_child(root)

        heading = Gtk.Label(label="Predator Control")
        heading.add_css_class("title-1")
        heading.set_halign(Gtk.Align.START)
        root.append(heading)

        subtitle = Gtk.Label(label="Acer Predator Helios 16 · Linux monitoring preview")
        subtitle.add_css_class("dim-label")
        subtitle.set_halign(Gtk.Align.START)
        root.append(subtitle)

        self.battery_grid = self.add_section(root, "Battery")
        self.thermal_grid = self.add_section(root, "Fans & temperatures")
        self.profile_grid = self.add_section(root, "Performance profile")

        self.note = Gtk.Label(
            label="Read-only preview. Fan/PWM writes and privileged changes are intentionally disabled."
        )
        self.note.set_wrap(True)
        self.note.set_halign(Gtk.Align.START)
        self.note.add_css_class("dim-label")
        root.append(self.note)

        refresh = Gtk.Button(label="Refresh now")
        refresh.set_halign(Gtk.Align.START)
        refresh.connect("clicked", lambda _button: self.refresh())
        root.append(refresh)

        self.refresh()
        GLib.timeout_add(REFRESH_MS, self.refresh)
        self.window.present()

    def add_section(self, root, title):
        frame = Gtk.Frame()
        frame.set_label(title)
        grid = Gtk.Grid(column_spacing=18, row_spacing=6)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        frame.set_child(grid)
        root.append(frame)
        return grid

    def set_grid(self, grid, values, prefix):
        child = grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            grid.remove(child)
            child = nxt

        for row, (label, value) in enumerate(values.items()):
            left = Gtk.Label(label=label)
            left.set_halign(Gtk.Align.START)
            left.add_css_class("dim-label")
            right = Gtk.Label(label=str(value))
            right.set_halign(Gtk.Align.END)
            right.set_selectable(True)
            grid.attach(left, 0, row, 1, 1)
            grid.attach(right, 1, row, 1, 1)

    def refresh(self, *_args):
        self.set_grid(self.battery_grid, battery_info(), "battery")
        thermal = thermal_info()
        if not thermal:
            thermal = {"Sensors": "No readable hwmon fan/temperature sensors found"}
        self.set_grid(self.thermal_grid, thermal, "thermal")

        current, choices = profile_info()
        self.set_grid(
            self.profile_grid,
            {"Current profile": current, "Available profiles": choices},
            "profile",
        )
        return GLib.SOURCE_CONTINUE


def main():
    app = PredatorControl()
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
