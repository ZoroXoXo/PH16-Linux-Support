#!/usr/bin/env python3
"""Predator Sense Arch Linux: hardware monitoring and platform-profile selection."""

import csv
import glob
import os
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

APP_TITLE = "Predator Sense Arch Linux"
REFRESH_MS = 2000
PROFILE_PATH = "/sys/firmware/acpi/platform_profile"
PROFILE_CHOICES_PATH = "/sys/firmware/acpi/platform_profile_choices"
PROFILE_HELPER = "/usr/local/libexec/predator-control-set-profile"


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, UnicodeError):
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

    bat = next((p for p in batteries if os.path.basename(p) == "BAT1"), batteries[0])
    result["Battery device"] = os.path.basename(bat)
    result["Charge"] = fmt_number(read_text(os.path.join(bat, "capacity")), "%")
    result["Status"] = read_text(os.path.join(bat, "status")) or "Not available"
    result["Cycle count"] = read_text(os.path.join(bat, "cycle_count")) or "Not exposed by kernel"

    charge_now = read_text(os.path.join(bat, "charge_now"))
    charge_full = read_text(os.path.join(bat, "charge_full"))
    charge_design = read_text(os.path.join(bat, "charge_full_design"))

    if charge_now:
        try:
            result["Remaining charge"] = f"{int(charge_now) / 1_000_000:.2f} Ah"
        except ValueError:
            pass

    if charge_full and charge_design:
        try:
            full_i, design_i = int(charge_full), int(charge_design)
            if full_i > 0 and design_i > 0:
                health = full_i / design_i * 100
                result["Estimated health"] = f"{health:.1f}%"
                result["Estimated wear"] = f"{max(0.0, 100.0 - health):.1f}%"
                result["Full-charge capacity"] = f"{full_i / 1_000_000:.2f} Ah"
                result["Design capacity"] = f"{design_i / 1_000_000:.2f} Ah"
                return result
        except ValueError:
            pass

    energy_now = read_text(os.path.join(bat, "energy_now"))
    energy_full = read_text(os.path.join(bat, "energy_full"))
    energy_design = read_text(os.path.join(bat, "energy_full_design"))
    if energy_now:
        try:
            result["Remaining energy"] = f"{int(energy_now) / 1_000_000:.2f} Wh"
        except ValueError:
            pass
    try:
        if energy_full and energy_design and int(energy_full) > 0 and int(energy_design) > 0:
            health = int(energy_full) / int(energy_design) * 100
            result["Estimated health"] = f"{health:.1f}%"
            result["Estimated wear"] = f"{max(0.0, 100.0 - health):.1f}%"
            result["Full-charge capacity"] = f"{int(energy_full) / 1_000_000:.2f} Wh"
            result["Design capacity"] = f"{int(energy_design) / 1_000_000:.2f} Wh"
        else:
            result["Estimated health"] = "Not exposed by kernel"
    except ValueError:
        result["Estimated health"] = "Not available"

    return result


def thermal_info():
    """Discover hwmon devices dynamically; never write to fan/PWM files."""
    result = {}
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name = read_text(os.path.join(hwmon, "name")) or os.path.basename(hwmon)

        for path in sorted(glob.glob(os.path.join(hwmon, "fan*_input"))):
            stem = os.path.basename(path).replace("_input", "")
            value = read_text(path)
            if value and value.isdigit():
                result[f"{name}: {stem}"] = f"{int(value)} RPM"

        for path in sorted(glob.glob(os.path.join(hwmon, "temp*_input"))):
            stem = os.path.basename(path).replace("_input", "")
            value = read_text(path)
            if not value:
                continue
            try:
                celsius = int(value) / 1000.0
            except ValueError:
                continue
            label = read_text(os.path.join(hwmon, stem + "_label")) or stem
            result[f"{name}: {label}"] = f"{celsius:.1f} °C"

    return result


def gpu_info():
    """Read NVIDIA telemetry via nvidia-smi; gracefully handle unavailable NVML."""
    query = (
        "name,temperature.gpu,utilization.gpu,memory.used,memory.total,"
        "power.draw,power.limit"
    )
    try:
        proc = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            text=True, capture_output=True, check=False, timeout=4,
        )
    except FileNotFoundError:
        return {"GPU telemetry": "nvidia-smi not installed"}
    except subprocess.TimeoutExpired:
        return {"GPU telemetry": "nvidia-smi timed out"}

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "Unknown NVIDIA telemetry error").strip()
        return {"GPU telemetry": f"Unavailable: {detail[-180:]}"}

    try:
        row = next(csv.reader([proc.stdout.strip()]))
    except (StopIteration, csv.Error):
        return {"GPU telemetry": "No GPU data returned"}

    if len(row) < 7:
        return {"GPU telemetry": "Unexpected nvidia-smi output"}

    name, temp, util, mem_used, mem_total, power, power_limit = [v.strip() for v in row[:7]]
    result = {"GPU": name or "NVIDIA GPU"}
    result["GPU temperature"] = fmt_number(temp, " °C") if temp not in ("", "N/A", "[Not Supported]") else "Not available"
    result["GPU utilization"] = fmt_number(util, "%") if util not in ("", "N/A", "[Not Supported]") else "Not available"

    if mem_used not in ("", "N/A", "[Not Supported]") and mem_total not in ("", "N/A", "[Not Supported]"):
        result["VRAM"] = f"{mem_used} / {mem_total} MiB"
    else:
        result["VRAM"] = "Not available"

    if power not in ("", "N/A", "[Not Supported]") and power_limit not in ("", "N/A", "[Not Supported]"):
        result["GPU power"] = f"{power} / {power_limit} W"
    elif power not in ("", "N/A", "[Not Supported]"):
        result["GPU power"] = f"{power} W"
    else:
        result["GPU power"] = "Not available"
    return result


def platform_profiles():
    current = read_text(PROFILE_PATH) or "Not exposed"
    choices = (read_text(PROFILE_CHOICES_PATH) or "").split()
    return current, choices


class PredatorControl(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.predatorsense.archlinux")
        self.window = None
        self.profile_dropdown = None
        self.profile_status = None
        self.profile_model_values = []

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self, title=APP_TITLE)
        self.window.set_default_size(760, 820)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.window.set_child(scroller)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)
        scroller.set_child(root)

        heading = Gtk.Label(label="Predator Sense Arch Linux")
        heading.add_css_class("title-1")
        heading.set_halign(Gtk.Align.START)
        root.append(heading)

        subtitle = Gtk.Label(label="Acer Predator Helios 16 · Hardware monitoring and platform profiles")
        subtitle.add_css_class("dim-label")
        subtitle.set_halign(Gtk.Align.START)
        root.append(subtitle)

        self.battery_grid = self.add_section(root, "Battery")
        self.thermal_grid = self.add_section(root, "Fans & temperatures")
        self.gpu_grid = self.add_section(root, "NVIDIA GPU")
        self.profile_grid = self.add_section(root, "Performance profile")

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_halign(Gtk.Align.START)
        root.append(controls)

        self.profile_dropdown = Gtk.DropDown.new_from_strings([])
        self.profile_dropdown.set_size_request(230, -1)
        controls.append(self.profile_dropdown)

        apply_button = Gtk.Button(label="Apply profile")
        apply_button.connect("clicked", self.apply_profile)
        controls.append(apply_button)

        self.profile_status = Gtk.Label(label="Profile changes require authorization.")
        self.profile_status.set_wrap(True)
        self.profile_status.set_halign(Gtk.Align.START)
        root.append(self.profile_status)

        note = Gtk.Label(label=(
            "Monitoring is read-only. Fan/PWM writes, charge thresholds, RGB controls, "
            "and kernel-module changes remain disabled. Battery health and wear are "
            "estimates based on firmware-reported capacity."
        ))
        note.set_wrap(True)
        note.set_halign(Gtk.Align.START)
        note.add_css_class("dim-label")
        root.append(note)

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

    def set_grid(self, grid, values):
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
            right.set_wrap(True)
            grid.attach(left, 0, row, 1, 1)
            grid.attach(right, 1, row, 1, 1)

    def refresh(self, *_args):
        self.set_grid(self.battery_grid, battery_info())
        thermal = thermal_info() or {"Sensors": "No readable hwmon fan/temperature sensors found"}
        self.set_grid(self.thermal_grid, thermal)
        self.set_grid(self.gpu_grid, gpu_info())

        current, choices = platform_profiles()
        self.set_grid(self.profile_grid, {
            "Current profile": current,
            "Available profiles": " ".join(choices) if choices else "Not exposed",
        })

        if choices and choices != self.profile_model_values:
            self.profile_model_values = choices
            self.profile_dropdown.set_model(Gtk.StringList.new(choices))
        if choices and current in choices:
            self.profile_dropdown.set_selected(choices.index(current))
        return GLib.SOURCE_CONTINUE

    def apply_profile(self, _button):
        if not self.profile_model_values:
            self.profile_status.set_text("No platform profiles are exposed by the kernel.")
            return

        selected = self.profile_dropdown.get_selected()
        if selected >= len(self.profile_model_values):
            self.profile_status.set_text("Select a valid profile first.")
            return

        profile = self.profile_model_values[selected]
        if not os.path.exists(PROFILE_HELPER):
            self.profile_status.set_text(
                "Profile helper is not installed. Follow README.md to install the root-owned helper first."
            )
            return

        try:
            result = subprocess.run(
                ["pkexec", PROFILE_HELPER, profile],
                text=True, capture_output=True, check=False, timeout=60,
            )
        except FileNotFoundError:
            self.profile_status.set_text(
                "pkexec was not found. Install polkit and a graphical authentication agent."
            )
            return
        except subprocess.TimeoutExpired:
            self.profile_status.set_text("Authorization timed out.")
            return

        if result.returncode == 0:
            self.profile_status.set_text(f"Requested profile: {profile}")
            self.refresh()
        else:
            detail = (result.stderr or result.stdout or "Operation cancelled or failed").strip()
            self.profile_status.set_text(f"Could not apply profile: {detail[-300:]}")


def main():
    app = PredatorControl()
    app.run(None)


if __name__ == "__main__":
    main()
