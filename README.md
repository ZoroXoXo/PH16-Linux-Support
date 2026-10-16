# Predator Control MVP

A small, read-only GTK4 monitoring app for Linux, starting with the Acer Predator Helios 16 PH16-72.

## What it shows

- Battery charge, status, cycle count, and estimated full-charge health when the kernel exposes the required values.
- Fan RPM and temperature readings from `/sys/class/hwmon`.
- Current ACPI platform profile and the profiles the firmware advertises.
- Refreshes every two seconds.

## Deliberate safety limits

This MVP does **not** write to fan PWM files, change the platform profile, modify charge thresholds, or load/unload kernel modules. On this laptop, PWM files exist but their safe/manual-control behaviour has not been verified. The battery health percentage is an estimate based on kernel-reported full-charge capacity divided by design capacity, not a definitive battery diagnostic.

## Install dependencies on Arch Linux

```bash
sudo pacman -S --needed python gtk4 python-gobject
```

## Run

Extract the ZIP, then from the extracted directory:

```bash
python app.py
```

Do not run it with `sudo`; read-only sensor data should not need root privileges.

## Troubleshooting

If `import gi` fails, verify that `python-gobject` is installed and that `python` is the system Python from Arch. If the app opens but a sensor is missing, inspect the available kernel interfaces:

```bash
find /sys/class/power_supply -maxdepth 2 -type f
find /sys/class/hwmon -maxdepth 2 -type f
cat /sys/firmware/acpi/platform_profile
cat /sys/firmware/acpi/platform_profile_choices
```

This is a first prototype; verify the displayed values against `sensors` and `/sys/class/power_supply/BAT1` on the target laptop.
