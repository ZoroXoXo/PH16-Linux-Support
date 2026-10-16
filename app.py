#!/usr/bin/env python3
"""Predator Sense Arch Linux: hardware monitoring and platform-profile selection."""

import csv
import glob
import os
import subprocess
import time
from collections import deque

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


def find_acer_hwmon():
    """Return the Acer hwmon path without assuming a fixed hwmon number."""
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        if read_text(os.path.join(hwmon, "name")) == "acer":
            return hwmon
    return None


def fan_control_info():
    """Report fan telemetry and control modes; never write to PWM files."""
    hwmon = find_acer_hwmon()
    if not hwmon:
        return {
            "Fan controller": "Acer hwmon device not found",
            "Manual control": "Disabled — hardware interface not detected",
        }

    result = {}
    fan_paths = sorted(glob.glob(os.path.join(hwmon, "fan*_input")))
    if not fan_paths:
        result["Fan speed"] = "No Acer fan RPM attributes found"

    all_auto = True
    mode_count = 0
    for path in fan_paths:
        stem = os.path.basename(path).replace("_input", "")
        number = stem.removeprefix("fan")
        value = read_text(path)
        result[f"Fan {number} speed"] = f"{value} RPM" if value and value.isdigit() else "Not available"

        pwm_path = os.path.join(hwmon, f"pwm{number}")
        enable_path = os.path.join(hwmon, f"pwm{number}_enable")
        pwm_value = read_text(pwm_path)
        enable_value = read_text(enable_path)

        if pwm_value is not None:
            result[f"Fan {number} raw PWM"] = pwm_value
        if enable_value is not None:
            mode_count += 1
            if enable_value == "2":
                result[f"Fan {number} mode"] = "Automatic (driver reports mode 2)"
            else:
                result[f"Fan {number} mode"] = f"Mode value {enable_value} (not assumed safe)"
                all_auto = False
        else:
            result[f"Fan {number} mode"] = "Mode attribute not exposed"
            all_auto = False

    if mode_count and all_auto:
        result["Safety status"] = "All detected fan modes report automatic"
    else:
        result["Safety status"] = "Automatic mode not confirmed for every detected fan"

    result["Manual control"] = "Disabled pending model-specific validation"
    return result


def thermal_info():
    """Discover hwmon temperature sensors dynamically; never write to sysfs."""
    result = {}
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name = read_text(os.path.join(hwmon, "name")) or os.path.basename(hwmon)

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


def history_sample():
    """Collect one read-only sample for the in-memory history graph."""
    sample = {"time": time.time(), "fan1": None, "fan2": None, "cpu": None, "gpu": None}
    acer = find_acer_hwmon()
    if acer:
        for key in ("fan1", "fan2"):
            value = read_text(os.path.join(acer, f"{key}_input"))
            try:
                sample[key] = float(value) if value is not None else None
            except ValueError:
                pass

    # Prefer the package temperature label instead of guessing a core number.
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        if read_text(os.path.join(hwmon, "name")) != "coretemp":
            continue
        for label_path in glob.glob(os.path.join(hwmon, "temp*_label")):
            if read_text(label_path) == "Package id 0":
                input_path = label_path[:-len("_label")] + "_input"
                value = read_text(input_path)
                try:
                    sample["cpu"] = float(value) / 1000.0 if value is not None else None
                except ValueError:
                    pass
                break
        break

    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True, capture_output=True, check=False, timeout=3,
        )
        if proc.returncode == 0:
            value = proc.stdout.strip().splitlines()[0].strip()
            if value not in ("", "N/A", "[Not Supported]"):
                sample["gpu"] = float(value)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass

    return sample


class HistoryGraph(Gtk.DrawingArea):
    """Small live chart; samples are held in memory and are never written to disk."""

    def __init__(self, history):
        super().__init__()
        self.history = history
        self.set_content_height(370)
        self.set_hexpand(True)
        self.set_draw_func(self.draw)

    @staticmethod
    def _text(cr, x, y, value, size=10):
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(size)
        cr.move_to(x, y)
        cr.show_text(str(value))

    @staticmethod
    def _line(cr, points, color, line_width=1.8):
        if len(points) < 2:
            return
        cr.set_source_rgb(*color)
        cr.set_line_width(line_width)
        cr.move_to(points[0][0], points[0][1])
        for x, y in points[1:]:
            cr.line_to(x, y)
        cr.stroke()

    def draw(self, _area, cr, width, height, _user_data=None):
        # Use two panels so RPM and temperatures each have a meaningful scale.
        left, right = 54, max(60, width - 16)
        gap = 38
        panel_height = max(90, (height - gap - 48) / 2)
        top1, bottom1 = 28, 28 + panel_height
        top2, bottom2 = bottom1 + gap, bottom1 + gap + panel_height
        cr.set_source_rgb(0.50, 0.52, 0.55)
        self._text(cr, 8, 16, "Fan speed (RPM)", 11)
        self._text(cr, 8, top2 - 12, "Temperature (°C)", 11)

        data = list(self.history)
        if len(data) < 2:
            cr.set_source_rgb(0.50, 0.52, 0.55)
            self._text(cr, left + 8, top1 + 30, "Collecting samples…")
            self._text(cr, left + 8, top2 + 30, "CPU and GPU temperatures appear when available")
            return

        def draw_panel(top, bottom, low, high, ticks):
            cr.set_line_width(1)
            cr.set_source_rgba(0.50, 0.52, 0.55, 0.30)
            for tick in ticks:
                y = bottom - (tick - low) / (high - low) * (bottom - top)
                cr.move_to(left, y)
                cr.line_to(right, y)
                cr.stroke()
                cr.set_source_rgb(0.50, 0.52, 0.55)
                self._text(cr, 5, y + 3, str(tick), 9)
                cr.set_source_rgba(0.50, 0.52, 0.55, 0.30)

        draw_panel(top1, bottom1, 0, 6000, (0, 2000, 4000, 6000))
        draw_panel(top2, bottom2, 20, 100, (20, 40, 60, 80, 100))

        t0, t1 = data[0]["time"], data[-1]["time"]
        span = max(1.0, t1 - t0)

        def points_for(key, top, bottom, low, high):
            points = []
            for item in data:
                value = item.get(key)
                if value is None:
                    continue
                x = left + (item["time"] - t0) / span * (right - left)
                value = max(low, min(high, value))
                y = bottom - (value - low) / (high - low) * (bottom - top)
                points.append((x, y))
            return points

        # Distinct colors identify series; the graph is observational only.
        self._line(cr, points_for("fan1", top1, bottom1, 0, 6000), (0.20, 0.55, 0.85))
        self._line(cr, points_for("fan2", top1, bottom1, 0, 6000), (0.85, 0.45, 0.20))
        self._line(cr, points_for("cpu", top2, bottom2, 20, 100), (0.75, 0.25, 0.25))
        self._line(cr, points_for("gpu", top2, bottom2, 20, 100), (0.20, 0.60, 0.35))

        cr.set_source_rgb(0.20, 0.55, 0.85)
        self._text(cr, left, height - 8, "Fan 1")
        cr.set_source_rgb(0.85, 0.45, 0.20)
        self._text(cr, left + 58, height - 8, "Fan 2")
        cr.set_source_rgb(0.75, 0.25, 0.25)
        self._text(cr, left + 116, height - 8, "CPU package")
        cr.set_source_rgb(0.20, 0.60, 0.35)
        self._text(cr, left + 218, height - 8, "GPU")
        cr.set_source_rgb(0.50, 0.52, 0.55)
        self._text(cr, max(left, right - 82), height - 8, f"{int(span)}s window")


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
        self.fan_grid = self.add_section(root, "Fan monitoring and safety")
        self.thermal_grid = self.add_section(root, "Temperature sensors")
        self.gpu_grid = self.add_section(root, "NVIDIA GPU")
        self.profile_grid = self.add_section(root, "Performance profile")

        history_frame = Gtk.Frame()
        history_frame.set_label("Live history · last 6 minutes")
        history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        history_box.set_margin_top(8)
        history_box.set_margin_bottom(8)
        history_box.set_margin_start(8)
        history_box.set_margin_end(8)
        self.history = deque(maxlen=180)
        self.history_graph = HistoryGraph(self.history)
        history_box.append(self.history_graph)
        history_hint = Gtk.Label(
            label="Fan RPM and CPU/GPU temperatures. Samples stay in memory only; nothing is logged to disk."
        )
        history_hint.set_wrap(True)
        history_hint.set_halign(Gtk.Align.START)
        history_hint.add_css_class("dim-label")
        history_box.append(history_hint)
        history_frame.set_child(history_box)
        root.append(history_frame)

        self.fan_safety_note = Gtk.Label(
            label=(
                "Manual fan control is intentionally disabled. The app only reads "
                "fan RPM, PWM values, and driver-reported modes; it never writes to "
                "PWM files or changes the embedded controller."
            )
        )
        self.fan_safety_note.set_wrap(True)
        self.fan_safety_note.set_halign(Gtk.Align.START)
        self.fan_safety_note.add_css_class("dim-label")
        root.append(self.fan_safety_note)

        self.manual_fan_button = Gtk.Button(
            label="Manual fan control disabled — validation pending"
        )
        self.manual_fan_button.set_sensitive(False)
        self.manual_fan_button.set_tooltip_text(
            "Disabled until manual control and recovery to automatic mode are verified "
            "for this laptop and kernel driver."
        )
        self.manual_fan_button.set_halign(Gtk.Align.START)
        root.append(self.manual_fan_button)

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
        self.set_grid(self.fan_grid, fan_control_info())
        thermal = thermal_info() or {"Sensors": "No readable hwmon temperature sensors found"}
        self.set_grid(self.thermal_grid, thermal)
        self.set_grid(self.gpu_grid, gpu_info())
        self.history.append(history_sample())
        self.history_graph.queue_draw()

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
