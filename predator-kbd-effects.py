#!/usr/bin/env python3
"""Persistent-connection RGB animations using the tested lamparray-kbd implementation."""
import colorsys
import importlib.util
import math
import random
import signal
import sys
import time
from pathlib import Path

TOOL_CANDIDATES = [
    Path.home() / ".local/bin/lamparray-kbd",
    Path("/usr/bin/lamparray-kbd"),
]
stop = False


def stop_handler(_sig, _frame):
    global stop
    stop = True


signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)


def rgb(value):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        raise ValueError("Invalid RGB colour; use a 3- or 6-digit hex value")


def scaled(color, factor):
    factor = max(0.0, min(1.0, factor))
    return tuple(max(0, min(255, round(c * factor))) for c in color)


def hue_color(hue, brightness=1.0):
    channels = colorsys.hsv_to_rgb(hue % 1.0, 1.0, 1.0)
    return scaled(tuple(round(c * 255) for c in channels), brightness)


def main():
    global stop
    if len(sys.argv) != 5:
        print("Usage: predator-kbd-effects.py EFFECT HEXCOLOUR BRIGHTNESS SPEED",
              file=sys.stderr)
        return 2

    effect = sys.argv[1].lower()
    base = rgb(sys.argv[2])
    brightness = max(0, min(100, int(sys.argv[3]))) / 100
    speed = max(1, min(10, int(sys.argv[4])))

    tool = next((p for p in TOOL_CANDIDATES
                 if p.is_file() and p.stat().st_mode & 0o111), None)
    if tool is None:
        print("lamparray-kbd not found", file=sys.stderr)
        return 2

    # Load the same tested implementation used by the CLI.
    import types
    module = types.ModuleType("lamparray_kbd")
    module.__file__ = str(tool)
    module.__package__ = ""
    try:
        source = tool.read_text()
        exec(compile(source, str(tool), "exec"), module.__dict__)
    except (OSError, SyntaxError) as exc:
        print(f"Could not load lamparray-kbd: {exc}", file=sys.stderr)
        return 2

    devices = module.discover()
    device = next((d for d in devices if d["id"] == "05af:666a"), None)
    if device is None:
        print("Acer keyboard LampArray 05af:666a not found", file=sys.stderr)
        return 2

    kb = None
    try:
        kb = module.LampArray(device)
        lamps = kb.lamps()
        if not lamps:
            print("Keyboard reported no lamps", file=sys.stderr)
            return 2

        # Stable physical order for moving effects.
        ordered = sorted(lamps, key=lambda l: (l["y"], l["x"], l["id"]))
        count = len(ordered)
        xs = [l["x"] for l in lamps]
        min_x, max_x = min(xs), max(xs)
        span_x = max(1, max_x - min_x)
        rng = random.Random()
        phase = 0
        frame_period = max(kb.min_interval / 1_000_000,
                           0.30 - (speed - 1) * 0.025)

        # Restore firmware-controlled lighting when stopped, if possible.
        kb.autonomous(False)
        while not stop:
            started = time.monotonic()
            mapping = {}

            for index, lamp in enumerate(ordered):
                x = (lamp["x"] - min_x) / span_x
                color = scaled(base, brightness)

                if effect == "breathing":
                    level = 0.12 + 0.88 * (
                        0.5 - 0.5 * math.cos(2 * math.pi * phase / 36)
                    )
                    color = scaled(base, brightness * level)

                elif effect == "wave":
                    color = hue_color(phase / 48 + x * 0.8, brightness)

                elif effect == "shifting":
                    color = hue_color(phase / 48, brightness)

                elif effect == "meteor":
                    head = (phase * 2) % count
                    distance = (index - head) % count
                    if distance == 0:
                        color = scaled((255, 255, 255), brightness)
                    elif distance <= 5:
                        color = scaled(base, brightness * (6 - distance) / 6)
                    else:
                        color = (0, 0, 0)

                elif effect == "snake":
                    head = (phase * 2) % count
                    distance = (index - head) % count
                    color = (scaled(base, brightness * (1 - distance / 9))
                             if distance < 8 else (0, 0, 0))

                elif effect == "twinkling":
                    color = scaled(base, brightness * 0.06)
                    if rng.random() < 0.12:
                        color = hue_color(rng.random(), brightness)

                else:
                    print(f"Unknown effect: {effect}", file=sys.stderr)
                    return 2

                mapping[lamp["id"]] = color

            kb.multi(mapping)
            phase += 1
            remaining = frame_period - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)

    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Animation stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        if kb is not None:
            try:
                kb.autonomous(True)
            except OSError:
                pass
            try:
                import os
                os.close(kb.fd)
            except OSError:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
