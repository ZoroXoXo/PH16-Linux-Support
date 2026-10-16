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
LIGHTING_TOOL_CANDIDATES = [os.path.expanduser("~/.local/bin/lamparray-kbd"), "/usr/bin/lamparray-kbd"]
ANIMATION_HELPER_NAME = "predator-kbd-effects.py"
LIGHTING_ANIMATIONS = ["Breathing", "Wave", "Meteor", "Snake", "Twinkling", "Shifting"]
LIGHTING_PRESETS = {
    "Predator Blue": "0080ff",
    "Ice White": "dcecff",
    "Red": "ff3030",
    "Purple": "a050ff",
    "Green": "30d878",
    "Cyan": "00d7ff",
    "Amber": "ff9f1c",
    "Pink": "ff4fa3",
}


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


def lighting_tool():
    """Find the per-user or system-installed lamparray-kbd executable."""
    for candidate in LIGHTING_TOOL_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def run_lighting_command(*args):
    """Run the keyboard lighting utility without a shell or elevated privileges."""
    tool = lighting_tool()
    if not tool:
        return False, "lamparray-kbd not found. Install it in ~/.local/bin first."
    try:
        result = subprocess.run(
            [tool, *map(str, args)],
            text=True, capture_output=True, check=False, timeout=20,
        )
    except subprocess.TimeoutExpired:
        return False, "Lighting command timed out."
    except OSError as exc:
        return False, f"Could not run lighting utility: {exc}"
    if result.returncode == 0:
        return True, (result.stdout or "Lighting command completed.").strip()
    detail = (result.stderr or result.stdout or "Lighting command failed").strip()
    return False, detail[-260:]


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
        self.lighting_preset = None
        self.lighting_brightness = None
        self.lighting_mode = None
        self.lighting_colors = None
        self.lighting_keys = None
        self.lighting_status = None
        self.lighting_animation = None
        self.lighting_speed = None
        self.animation_process = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self, title=APP_TITLE)
        self.window.set_default_size(1080, 760)
        self.window.set_size_request(760, 600)

        # App-local styling: restrained graphite surfaces and Predator-red accent.
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background: #111318; color: #e8eaf0; }
            .app-header { padding: 18px 22px 12px 22px; }
            .app-title { font-size: 24px; font-weight: 800; color: #f4f5f7; }
            .app-subtitle { color: #a4a9b4; font-size: 13px; }
            .page-title { font-size: 18px; font-weight: 750; padding-bottom: 4px; }
            .metric-card { background: #1b1e25; border: 1px solid #303540; border-radius: 12px; padding: 14px; }
            .metric-label { color: #a4a9b4; font-size: 12px; }
            .metric-value { color: #f5f6f8; font-size: 23px; font-weight: 750; }
            .accent { color: #ff454f; }
            frame { border: 1px solid #303540; border-radius: 10px; }
            frame > label { color: #ff626a; font-weight: 650; padding: 0 5px; }
            entry, dropdown, spinbutton { border-radius: 7px; }
            button { border-radius: 8px; padding: 7px 12px; }
            button.suggested-action { background: #d92d3a; color: white; }
            .page-content { padding: 18px; }
            .dim-label { color: #a4a9b4; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window.set_child(outer)
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header.add_css_class("app-header")
        title = Gtk.Label(label="PREDATOR SENSE")
        title.add_css_class("app-title")
        title.set_halign(Gtk.Align.START)
        subtitle = Gtk.Label(label="ARCH LINUX  /  HELIOS 16  ·  SYSTEM CONTROL")
        subtitle.add_css_class("app-subtitle")
        subtitle.set_halign(Gtk.Align.START)
        header.append(title)
        header.append(subtitle)
        outer.append(header)

        switcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        switcher_box.set_margin_start(20)
        switcher_box.set_margin_end(20)
        switcher_box.set_margin_bottom(8)
        outer.append(switcher_box)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(140)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_halign(Gtk.Align.START)
        switcher_box.append(switcher)
        outer.append(self.stack)

        def make_page(name):
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            content.add_css_class("page-content")
            content.set_margin_start(2)
            content.set_margin_end(2)
            scroller.set_child(content)
            self.stack.add_titled(scroller, name.lower().replace(" ", "-"), name)
            return content

        def page_heading(parent, text):
            label = Gtk.Label(label=text)
            label.add_css_class("page-title")
            label.set_halign(Gtk.Align.START)
            parent.append(label)

        # Dashboard: the most useful status blocks first.
        dashboard = make_page("Dashboard")
        page_heading(dashboard, "System overview")
        metrics = Gtk.Grid(column_spacing=10, row_spacing=10)
        metrics.set_column_homogeneous(True)
        dashboard.append(metrics)
        self.metric_labels = {}
        for i, (key, label) in enumerate([
            ("cpu", "CPU PACKAGE"), ("gpu", "GPU TEMP"),
            ("fan1", "FAN 1 RPM"), ("fan2", "FAN 2 RPM")
        ]):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            card.add_css_class("metric-card")
            top = Gtk.Label(label=label)
            top.add_css_class("metric-label")
            top.set_halign(Gtk.Align.START)
            value = Gtk.Label(label="Collecting…")
            value.add_css_class("metric-value")
            value.set_halign(Gtk.Align.START)
            card.append(top)
            card.append(value)
            metrics.attach(card, i % 2, i // 2, 1, 1)
            self.metric_labels[key] = value

        self.battery_grid = self.add_section(dashboard, "Battery")
        self.fan_grid = self.add_section(dashboard, "Fan monitoring & safety")
        self.gpu_grid = self.add_section(dashboard, "NVIDIA GPU")

        profile_page = make_page("Performance")
        page_heading(profile_page, "Performance profile")
        profile_intro = Gtk.Label(label="Choose a platform profile exposed by your kernel. Changes require authorization.")
        profile_intro.set_wrap(True)
        profile_intro.set_halign(Gtk.Align.START)
        profile_intro.add_css_class("dim-label")
        profile_page.append(profile_intro)
        self.profile_grid = self.add_section(profile_page, "Current system profile")
        profile_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        profile_controls.set_hexpand(True)
        self.profile_dropdown = Gtk.DropDown.new_from_strings([])
        self.profile_dropdown.set_hexpand(True)
        profile_controls.append(self.profile_dropdown)
        apply_button = Gtk.Button(label="Apply profile")
        apply_button.add_css_class("suggested-action")
        apply_button.connect("clicked", self.apply_profile)
        profile_controls.append(apply_button)
        profile_page.append(profile_controls)
        self.profile_status = Gtk.Label(label="Profile changes require authorization.")
        self.profile_status.set_wrap(True)
        self.profile_status.set_halign(Gtk.Align.START)
        self.profile_status.add_css_class("dim-label")
        profile_page.append(self.profile_status)
        self.manual_fan_button = Gtk.Button(label="Manual fan control disabled — validation pending")
        self.manual_fan_button.set_sensitive(False)
        self.manual_fan_button.set_tooltip_text(
            "Disabled until manual control and recovery to automatic mode are verified for this laptop and kernel driver."
        )
        self.manual_fan_button.set_halign(Gtk.Align.START)
        profile_page.append(self.manual_fan_button)
        self.fan_safety_note = Gtk.Label(label=(
            "Safety: monitoring is read-only. The app never writes to PWM files or changes the embedded controller."
        ))
        self.fan_safety_note.set_wrap(True)
        self.fan_safety_note.set_halign(Gtk.Align.START)
        self.fan_safety_note.add_css_class("dim-label")
        profile_page.append(self.fan_safety_note)

        lighting_page = make_page("Keyboard RGB")
        page_heading(lighting_page, "Keyboard lighting")
        lighting_intro = Gtk.Label(label="Custom colours and animated effects for the built-in keyboard LampArray.")
        lighting_intro.set_wrap(True)
        lighting_intro.set_halign(Gtk.Align.START)
        lighting_intro.add_css_class("dim-label")
        lighting_page.append(lighting_intro)
        self.lighting_grid = self.add_section(lighting_page, "Lighting controls")
        self.lighting_grid.attach(Gtk.Label(label="Mode", halign=Gtk.Align.START), 0, 0, 1, 1)
        self.lighting_mode = Gtk.DropDown.new_from_strings(["Solid colour", "Gradient", "Zones", "Per-key", "Animated"])
        self.lighting_mode.set_selected(0)
        self.lighting_mode.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_mode, 1, 0, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Base preset", halign=Gtk.Align.START), 0, 1, 1, 1)
        self.lighting_preset = Gtk.DropDown.new_from_strings(list(LIGHTING_PRESETS.keys()))
        self.lighting_preset.set_selected(0)
        self.lighting_preset.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_preset, 1, 1, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Gradient / zone colours", halign=Gtk.Align.START), 0, 2, 1, 1)
        self.lighting_colors = Gtk.Entry()
        self.lighting_colors.set_placeholder_text("ff0000, ff8800, 0000ff")
        self.lighting_colors.set_text("ff0000, 0000ff")
        self.lighting_colors.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_colors, 1, 2, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Per-key overrides", halign=Gtk.Align.START), 0, 3, 1, 1)
        self.lighting_keys = Gtk.Entry()
        self.lighting_keys.set_placeholder_text("w=00aaff a=00aaff s=00aaff d=00aaff")
        self.lighting_keys.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_keys, 1, 3, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Animated effect", halign=Gtk.Align.START), 0, 4, 1, 1)
        self.lighting_animation = Gtk.DropDown.new_from_strings(LIGHTING_ANIMATIONS)
        self.lighting_animation.set_selected(1)
        self.lighting_animation.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_animation, 1, 4, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Animation speed", halign=Gtk.Align.START), 0, 5, 1, 1)
        self.lighting_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 10, 1)
        self.lighting_speed.set_value(5)
        self.lighting_speed.set_draw_value(True)
        self.lighting_speed.set_value_pos(Gtk.PositionType.RIGHT)
        self.lighting_speed.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_speed, 1, 5, 1, 1)
        self.lighting_grid.attach(Gtk.Label(label="Brightness", halign=Gtk.Align.START), 0, 6, 1, 1)
        self.lighting_brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.lighting_brightness.set_value(100)
        self.lighting_brightness.set_draw_value(True)
        self.lighting_brightness.set_value_pos(Gtk.PositionType.RIGHT)
        self.lighting_brightness.set_hexpand(True)
        self.lighting_grid.attach(self.lighting_brightness, 1, 6, 1, 1)
        lighting_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lighting_buttons.set_halign(Gtk.Align.START)
        self.lighting_grid.attach(lighting_buttons, 0, 7, 2, 1)
        apply_lighting = Gtk.Button(label="Apply effect")
        apply_lighting.add_css_class("suggested-action")
        apply_lighting.connect("clicked", self.apply_lighting)
        lighting_buttons.append(apply_lighting)
        auto_lighting = Gtk.Button(label="Firmware lighting")
        auto_lighting.connect("clicked", self.set_firmware_lighting)
        lighting_buttons.append(auto_lighting)
        stop_lighting = Gtk.Button(label="Stop animation")
        stop_lighting.connect("clicked", self.stop_lighting_animation)
        lighting_buttons.append(stop_lighting)
        lighting_hint = Gtk.Label(label=(
            "Gradient and Zones use comma-separated colours. Per-key overrides use key names from lamparray-kbd info."
        ))
        lighting_hint.set_wrap(True)
        lighting_hint.set_halign(Gtk.Align.START)
        lighting_hint.add_css_class("dim-label")
        self.lighting_grid.attach(lighting_hint, 0, 8, 2, 1)
        self.lighting_status = Gtk.Label(label="Choose a mode and apply it. Firmware lighting restores the keyboard's built-in effect.")
        self.lighting_status.set_wrap(True)
        self.lighting_status.set_halign(Gtk.Align.START)
        self.lighting_status.add_css_class("dim-label")
        self.lighting_grid.attach(self.lighting_status, 0, 9, 2, 1)

        monitoring_page = make_page("Monitoring")
        page_heading(monitoring_page, "Sensors & live history")
        self.thermal_grid = self.add_section(monitoring_page, "Temperature sensors")
        history_frame = Gtk.Frame()
        history_frame.set_label("Live history · last 6 minutes")
        history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        history_box.set_margin_top(10)
        history_box.set_margin_bottom(10)
        history_box.set_margin_start(12)
        history_box.set_margin_end(12)
        self.history = deque(maxlen=180)
        self.history_graph = HistoryGraph(self.history)
        history_box.append(self.history_graph)
        history_hint = Gtk.Label(label="Fan RPM and CPU/GPU temperatures. Samples stay in memory only; nothing is logged to disk.")
        history_hint.set_wrap(True)
        history_hint.set_halign(Gtk.Align.START)
        history_hint.add_css_class("dim-label")
        history_box.append(history_hint)
        history_frame.set_child(history_box)
        monitoring_page.append(history_frame)
        refresh = Gtk.Button(label="Refresh now")
        refresh.set_halign(Gtk.Align.START)
        refresh.connect("clicked", lambda _button: self.refresh())
        monitoring_page.append(refresh)
        note = Gtk.Label(label=(
            "Battery health and wear are estimates based on firmware-reported capacity. Sensor availability depends on the kernel and hardware."
        ))
        note.set_wrap(True)
        note.set_halign(Gtk.Align.START)
        note.add_css_class("dim-label")
        monitoring_page.append(note)

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
        gpu = gpu_info()
        self.set_grid(self.gpu_grid, gpu)
        sample = history_sample()
        if hasattr(self, "metric_labels"):
            self.metric_labels["cpu"].set_text(f"{sample['cpu']:.1f} °C" if sample["cpu"] is not None else "—")
            self.metric_labels["gpu"].set_text(f"{sample['gpu']:.1f} °C" if sample["gpu"] is not None else "—")
            self.metric_labels["fan1"].set_text(f"{sample['fan1']:.0f} RPM" if sample["fan1"] is not None else "—")
            self.metric_labels["fan2"].set_text(f"{sample['fan2']:.0f} RPM" if sample["fan2"] is not None else "—")
        self.history.append(sample)
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

    def stop_lighting_animation(self, _button=None):
        process = self.animation_process
        self.animation_process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        return process is not None

    def start_lighting_animation(self, base_color, brightness):
        self.stop_lighting_animation()
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), ANIMATION_HELPER_NAME)
        if not os.path.isfile(helper):
            self.lighting_status.set_text(f"Animation helper not found: {helper}. Keep it beside app.py.")
            return
        selected = self.lighting_animation.get_selected()
        if selected >= len(LIGHTING_ANIMATIONS):
            self.lighting_status.set_text("Select an animation first.")
            return
        effect = LIGHTING_ANIMATIONS[selected].lower()
        speed = int(round(self.lighting_speed.get_value()))
        try:
            self.animation_process = subprocess.Popen(
                ["python", helper, effect, base_color, str(brightness), str(speed)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError as exc:
            self.lighting_status.set_text(f"Could not start animation: {exc}")
            return
        self.lighting_status.set_text(f"Running {effect.title()} at speed {speed}/10. Use Stop animation to end it.")

    def apply_lighting(self, _button):
        if any(value is None for value in (
            self.lighting_preset, self.lighting_brightness, self.lighting_mode,
            self.lighting_colors, self.lighting_keys, self.lighting_status,
        )):
            return

        preset_names = list(LIGHTING_PRESETS.keys())
        preset_index = self.lighting_preset.get_selected()
        if preset_index >= len(preset_names):
            self.lighting_status.set_text("Select a base colour preset first.")
            return
        preset_name = preset_names[preset_index]
        base_color = LIGHTING_PRESETS[preset_name]
        brightness = int(round(self.lighting_brightness.get_value()))
        mode_index = self.lighting_mode.get_selected()
        mode_names = ["Solid colour", "Gradient", "Zones", "Per-key", "Animated"]
        if mode_index >= len(mode_names):
            self.lighting_status.set_text("Select a lighting mode.")
            return
        if mode_index == 4:
            self.start_lighting_animation(base_color, brightness)
            return
        self.stop_lighting_animation()
        args = ["-b", str(brightness)]
        if mode_index == 0:
            args += ["solid", base_color]
            description = f"{preset_name} solid colour"
        elif mode_index in (1, 2):
            colors = [part.strip().lstrip("#") for part in self.lighting_colors.get_text().split(",") if part.strip()]
            if len(colors) < 2:
                self.lighting_status.set_text("Enter at least two comma-separated colours, e.g. ff0000, 0000ff.")
                return
            import re
            valid_color = re.compile(r"^(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|red|green|blue|white|cyan|magenta|yellow|orange|purple|pink|teal|warmwhite|coolwhite|off|black)$", re.IGNORECASE)
            if any(not valid_color.fullmatch(color) for color in colors):
                self.lighting_status.set_text("Use 3- or 6-digit hex colours or supported colour names; separate them with commas.")
                return
            args += ["gradient" if mode_index == 1 else "zones", *colors]
            description = ("Gradient" if mode_index == 1 else f"{len(colors)}-zone lighting") + f" ({', '.join(colors)})"
        else:
            overrides_text = self.lighting_keys.get_text().strip()
            if not overrides_text:
                self.lighting_status.set_text("Enter per-key overrides, e.g. w=00aaff a=00aaff s=00aaff d=00aaff.")
                return
            import re
            tokens = overrides_text.split()
            valid_color = re.compile(r"^(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|red|green|blue|white|cyan|magenta|yellow|orange|purple|pink|teal|warmwhite|coolwhite|off|black)$", re.IGNORECASE)
            for token in tokens:
                if "=" not in token:
                    self.lighting_status.set_text(f"Invalid key override '{token}'. Use key=colour, e.g. w=00aaff.")
                    return
                key, color = token.split("=", 1)
                if not key or not color or not valid_color.fullmatch(color.lstrip("#")):
                    self.lighting_status.set_text(f"Invalid key override '{token}'. Check the key name and colour.")
                    return
            args += ["keys", base_color, *tokens]
            description = f"{preset_name} base with {len(tokens)} per-key override(s)"

        ok, message = run_lighting_command(*args)
        if ok:
            self.lighting_status.set_text(f"Applied {description} at {brightness}% brightness.")
        else:
            self.lighting_status.set_text(f"Could not apply keyboard lighting: {message}")

    def set_firmware_lighting(self, _button):
        self.stop_lighting_animation()
        ok, message = run_lighting_command("auto")
        if ok:
            self.lighting_status.set_text(
                "Firmware lighting requested. The keyboard now controls its built-in effect."
            )
        else:
            self.lighting_status.set_text(f"Could not restore firmware lighting: {message}")

    def do_shutdown(self):
        self.stop_lighting_animation()
        Gtk.Application.do_shutdown(self)

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
