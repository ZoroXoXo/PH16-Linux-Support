# Predator Sense Arch Linux

A lightweight GTK4 prototype for monitoring and controlling selected platform features on Acer Predator laptops running Linux. Initial development target: Acer Predator Helios 16 PH16-72 on Arch Linux.

## Current features

- Battery charge, status, cycle count, and estimated full-charge health where the kernel exposes capacity data.
- Fan RPM and temperature readings from `/sys/class/hwmon`.
- Current platform profile and profiles exposed by the kernel.
- Optional platform-profile switching via a fixed-purpose privileged helper.
- Refreshes sensor data every two seconds.

## Install dependencies

```bash
sudo pacman -S --needed python gtk4 python-gobject polkit
```

A graphical PolicyKit authentication agent must also be running in your desktop session for `pkexec` prompts to appear. Desktop environments usually provide one; minimal window-manager setups may require installing/enabling an agent separately.

## Install the profile helper

From the project directory:

```bash
sudo ./install-profile-helper.sh
```

This installs `predator-control-set-profile` as a root-owned executable at `/usr/local/libexec/`. The helper validates the requested profile against a fixed allowlist and the kernel's advertised choices, then writes only to `/sys/firmware/acpi/platform_profile`.

Do not run the GTK app with `sudo`.

## Run

```bash
python app.py
```

Choose a profile and click **Apply profile**. The system may ask for authentication. If authorization is cancelled, the profile should remain unchanged.

## Safety notes

- Platform profiles are requests to firmware/kernel policy; they do not guarantee a specific CPU/GPU wattage or performance level.
- Fan/PWM writes, battery charge thresholds, RGB control, and kernel-module management are not implemented.
- Battery health is an estimate based on kernel-reported full-charge capacity divided by design capacity, not a definitive diagnostic.
- This is an early prototype; verify readings against `sensors` and the relevant `/sys` interfaces on your hardware.

## Development status

The GTK critical message observed during early testing did not prevent the window from working, but should be investigated separately. Test the app and profile helper on the target laptop before relying on it.
