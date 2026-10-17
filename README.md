
# PH16 LINUX SUPPORT

## A Linux-focused control and monitoring dashboard for Acer Predator hardware


## Disclaimer

**PH16-Linux-Support is an independent, community-developed project.** It is not affiliated with, endorsed by, sponsored by, or officially associated with Acer Inc. or its subsidiaries.

Acer, Predator, and related product names and trademarks belong to their respective owners and are used solely to identify compatible hardware and describe the project's purpose.

This project is provided on an **"as is"** basis, without warranties of any kind. Hardware support and functionality may vary by laptop model, firmware version, and Linux configuration. Use it at your own risk.

This project is not an official replacement for Acer's PredatorSense software.

------------------------------------------------------------------------------

**Built on Arch Linux · Hardware-aware · Open-source project**

> **Target hardware:** Acer Predator Helios 16 (PH16-72)  
> **Development environment:** Arch Linux  
> **Status:** Hardware-specific development; compatibility with other models has not been established.

PH16 Linux Support was developed and tested on the PH16-72. Sensor availability, performance-profile controls, and keyboard lighting may behave differently on other laptop models, firmware versions, and Linux configurations.

------------------------------------------------------------------------


## Why this project exists

Acer Predator laptops offer useful controls and system information
through PredatorSense on Windows, but comparable support can be limited
or fragmented on Linux. PH16-Linux-Support explores a unified interface for
viewing hardware telemetry and interacting with supported platform
controls from Arch Linux.

The goal is practical: make useful laptop information easier to inspect,
while keeping hardware control conservative and clearly communicating
what has---and has not---been validated.

## Screenshots

### System overview

![PH16-Linux-Support dashboard showing CPU and GPU temperatures, fan speeds,
battery information, performance profile, and GPU
telemetry](screenshots/predsense.png)

### Sensor monitoring and history

![Monitoring view showing temperature sensors and recent fan-speed and
temperature history](screenshots/monitor.png)

### Keyboard lighting

![Keyboard lighting interface with mode, preset, colour, per-key
override, animation, speed, and brightness
controls](screenshots/rgb.png)

### Performance profiles

![Performance profile interface showing the current balanced profile,
available profiles, and fan-control validation
notice](screenshots/perfor.png)

## Current functionality

| Area | Status | Notes |
|---|---|---|
| System dashboard | Implemented | Displays detected CPU/GPU telemetry, fan RPM, battery information, and the current performance profile. |
| Sensor monitoring | Implemented | Displays available sensor readings and recent in-memory history. Samples are not logged to disk. |
| Platform performance profiles | Implemented, hardware-dependent | Reads available platform profiles and requests authorization for profile changes. |
| Keyboard lighting | Interface present; hardware support requires verification | The interface exposes lighting controls. Verify individual modes and effects on the target keyboard before describing them as fully working. |
| Manual fan control | **Disabled / not validated** | Fan readings are monitoring-only. Manual control remains disabled pending model-specific validation. The app does not write PWM files or change the embedded controller. |

  -----------------------------------------------------------------------

> **Hardware compatibility matters.** Available sensors, profiles,
> keyboard-lighting behaviour, and control permissions can vary by
> laptop model, firmware, kernel, and installed services. Screenshots
> demonstrate the interface and observed readings on the development
> machine, not universal compatibility.

## Safety approach

-   Fan monitoring is read-only.
-   Manual fan control remains disabled until model-specific behaviour
    can be validated safely.
-   Performance-profile changes require authorization.
-   Do not assume a visible UI control is functional on every device;
    verify behaviour on the target hardware.

## Acknowledgements and Third-Party Projects

PH16 Linux Support was developed to address a gap in my Linux workflow on the Acer Predator Helios 16 (PH16-72). I wanted a convenient desktop interface for laptop controls and hardware monitoring on Arch Linux.

During development, I consulted existing open-source projects to research hardware interfaces and understand the available control mechanisms:

- **[Predator Sense for Linux](https://github.com/cleyton1986/predator-sense)** — consulted as a reference during research into Acer Predator hardware controls and Linux support.
- **[lamparray-kbd](https://github.com/usamathpc/lamparray-kbd)** — used for keyboard LampArray integration and lighting functionality.

PH16-Linux-Support provides its own GTK4 desktop interface, dashboard, telemetry presentation, performance-profile workflow, and application packaging. The project builds on existing Linux tooling where appropriate rather than claiming to implement every hardware interface from scratch.

Keyboard lighting depends on `lamparray-kbd`. Please refer to its upstream repository for its source, license, and attribution details.

Hardware support is model-specific. Fan RPM monitoring is separate from manual fan-speed control; manual fan control remains unverified on the PH16-72 and is not presented as a working feature.

### Licenses

PH16 Linux Support is licensed under the GNU General Public License v3.0 or later. The `lamparray-kbd` utility is a separate dependency; see its upstream repository for its license and notices. Other third-party projects retain their respective licenses.

## Development status

This is an actively developed, hardware-specific project. Some UI areas
and controls may need further validation. Contributions, issue reports,
and testing on other compatible Acer Predator models can help clarify
the support matrix.


