::: {align="center"}
# PREDATOR SENSE

### A Linux-focused control and monitoring dashboard for Acer Predator hardware

**Built on Arch Linux · Hardware-aware · Open-source project**

A practical attempt to close the gap between Acer's Windows-focused
PredatorSense utility and the tools available to Linux users.
:::

------------------------------------------------------------------------

## Why this project exists

Acer Predator laptops offer useful controls and system information
through PredatorSense on Windows, but comparable support can be limited
or fragmented on Linux. Predator Sense explores a unified interface for
viewing hardware telemetry and interacting with supported platform
controls from Arch Linux.

The goal is practical: make useful laptop information easier to inspect,
while keeping hardware control conservative and clearly communicating
what has---and has not---been validated.

## Screenshots

### System overview

![Predator Sense dashboard showing CPU and GPU temperatures, fan speeds,
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

  -----------------------------------------------------------------------
  Area                    Status                  Notes
  ----------------------- ----------------------- -----------------------
  System dashboard        Implemented             Presents detected
                                                  CPU/GPU telemetry, fan
                                                  RPM, battery
                                                  information, and
                                                  current performance
                                                  profile.

  Sensor monitoring       Implemented             Displays available
                                                  sensor readings and
                                                  recent in-memory
                                                  history. The UI notes
                                                  that samples are not
                                                  logged to disk.

  Platform performance    Implemented,            Reads available
  profiles                hardware-dependent      platform profiles and
                                                  requests authorization
                                                  for profile changes.

  Keyboard lighting       Interface present;      The screenshot shows
  interface               hardware support should lighting controls.
                          be verified             Confirm each mode and
                                                  effect on the target
                                                  keyboard before
                                                  describing it as fully
                                                  working.

  Manual fan control      **Disabled / not        Fan readings are
                          validated**             monitoring-only. Manual
                                                  control remains
                                                  disabled pending
                                                  model-specific
                                                  validation. The app
                                                  does not write PWM
                                                  files or change the
                                                  embedded controller.
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

## Implementation and acknowledgements

This project was developed to address a practical Linux tooling gap and
includes work built on or adapted from **two existing GitHub
repositories**.

**Upstream projects to credit before publishing:** 1.
`[Repository name]` --- \[URL\] --- describe the code or component
reused. 2. `[Repository name]` --- \[URL\] --- describe the code or
component reused.

Please replace these placeholders with the exact repositories and
identify the relevant files/components. Review each upstream project's
licence and preserve any required notices. This README intentionally
does not guess repository names or claim that all components were
written from scratch.

## Development status

This is an actively developed, hardware-specific project. Some UI areas
and controls may need further validation. Contributions, issue reports,
and testing on other compatible Acer Predator models can help clarify
the support matrix.

## Repository

GitHub:
[`predator-sense-arch-linux`](https://github.com/ZoroXoX/predator-sense-arch-linux)

------------------------------------------------------------------------

::: {align="center"}
**Predator Sense · Linux laptop tooling**

*Monitor what the system exposes. Keep unvalidated hardware controls
disabled.*
:::
