# Predator Sense

A lightweight GTK4 desktop application for monitoring and controlling supported hardware features on Acer Predator laptops running Arch Linux.

Predator Sense is being developed and tested on an **Acer Predator Helios 16 (PH16-72)** running Arch Linux. Hardware support may vary across laptop models, firmware versions, and Linux configurations.

## Features

- **Dashboard:** A compact overview of system status and hardware metrics.
- **Performance profiles:** View available platform profiles and apply supported profiles through the system's platform-profile interface.
- **Hardware monitoring:** Display available CPU and GPU temperatures, fan RPM readings, battery information, and NVIDIA telemetry.
- **Keyboard RGB:** Configure supported keyboard lighting, including colors, gradients, zones, per-key lighting, and animations.
- **Live monitoring:** View recent temperature and fan-speed history.
- **Desktop integration:** Launch Predator Sense from the application menu or terminal.

Unavailable hardware readings are shown when the relevant information is not exposed by the system.

## Requirements

- Arch Linux
- Python
- GTK4
- PyGObject (`python-gobject`)
- `nvidia-utils` for NVIDIA telemetry
- `pkexec` for authenticated performance-profile changes
- A supported Acer keyboard and the `lamparray-kbd` utility for keyboard lighting

Some features require additional system configuration. Keyboard lighting support depends on the laptop's hardware and access to its HID device.

## Installation

### Install the Arch package

If you have downloaded or built the package locally:

```bash
sudo pacman -U ./predator-sense-0.1.0-1-any.pkg.tar.zst
```

Launch the application with:

```bash
predator-sense
```

You can also search for **Predator Sense** in your desktop application's menu.

### Build from source

Clone or download this repository, then install the runtime dependencies:

```bash
sudo pacman -S python gtk4 python-gobject
```

For NVIDIA telemetry, install:

```bash
sudo pacman -S nvidia-utils
```

Build the Arch package from the project directory:

```bash
makepkg -f
```

Install the generated package:

```bash
sudo pacman -U ./predator-sense-0.1.0-1-any.pkg.tar.zst
```

The package recipe and generated package metadata are maintained in `PKGBUILD` and `.SRCINFO`.

## Keyboard lighting

Keyboard lighting is handled by the separate `lamparray-kbd` utility and the `predator-kbd-effects.py` animation helper.

The application expects the keyboard utility at one of these locations:

- `~/.local/bin/lamparray-kbd`
- `/usr/bin/lamparray-kbd`

The animation helper is installed alongside the application.

Keyboard lighting availability depends on the laptop's hardware, HID device access, and the utility's supported features.

## Performance profiles

Predator Sense uses the Linux platform-profile interface and a separate privileged helper to apply supported profiles.

The existing helper is located at:

```text
/usr/local/libexec/predator-control-set-profile
```

Profile changes require authorization through `pkexec`. Available profiles depend on the laptop firmware and the kernel configuration.

## Safety and limitations

- Fan RPM readings are monitoring-only. **Manual fan-speed control is intentionally disabled.**
- The application does not perform raw embedded-controller writes to control fans.
- Battery health and wear figures are estimates based on values exposed by the system.
- Temperatures, fan readings, GPU metrics, and other telemetry may be unavailable on some configurations.
- Performance-profile options depend on firmware and kernel support.
- Keyboard RGB features depend on compatible hardware and HID access.

This project is developed for personal use and is still evolving. Test hardware-control features carefully and report issues with relevant system details.

## Development

The main application is `app.py`. Keyboard animations are implemented in `predator-kbd-effects.py`.

Packaging files:

- `PKGBUILD` — Arch package recipe
- `.SRCINFO` — package metadata generated from `PKGBUILD`
- `predator-sense.png` — application icon
- `LICENSE` — MIT license

After changing `PKGBUILD`, regenerate package metadata:

```bash
makepkg --printsrcinfo > .SRCINFO
```

Build a new package:

```bash
makepkg -f
```

Install the updated build:

```bash
sudo pacman -U ./predator-sense-0.1.0-1-any.pkg.tar.zst
```

Generated build directories (`src/` and `pkg/`) and package archives should generally remain out of Git.

## License

Predator Sense is distributed under the MIT License. See [LICENSE](LICENSE) for details.
