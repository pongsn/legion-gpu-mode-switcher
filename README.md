# Legion GPU Mode Switcher

A lightweight KDE system tray application for switching GPU modes on Lenovo Legion laptops running the [lenovolegionlinux](https://github.com/johnfanv2/LenovoLegionLinux) driver.

## Features

- Shows current GPU mode in the system tray — GPU card icon (PCIe card body with two cooling fans and gold contact fingers): red/green split for Hybrid, solid green for dGPU only
- **In Hybrid mode**, the fan on the active GPU's side glows yellow to show which GPU is currently doing work — updates every 5 seconds via `/dev/nvidia*` usage detection
- Switch between **Hybrid (iGPU + dGPU)** and **dGPU only** with one click — menu labels are hardware-agnostic (iGPU/dGPU rather than AMD/NVIDIA)
- No password prompt for the active desktop session (polkit `allow_active: yes`)
- Tracks pending mode switches before reboot — shows an orange badge on the icon and allows cancelling the switch
- Triggers a reboot prompt after switching; also offers "Reboot now" from the tray menu
- Shows a **"Show dGPU processes"** menu item only when the dGPU is actually in use; lists all processes with an NVIDIA device open (graphics and compute — detected via `/proc/<pid>/fd`, not just CUDA via `nvidia-smi`)
- Popup dialogs share the same tray icon
- Installs itself as a KDE autostart entry

## Compatibility

| Component | Requirement |
|-----------|-------------|
| Hardware | Lenovo Legion laptop with MUX switch support via lenovolegionlinux |
| Init system | systemd (for `systemctl reboot`) |
| Desktop | Any DE with system tray support (KDE, XFCE, …). GNOME on Wayland requires the AppIndicator extension |
| Autostart | XDG-compliant DEs (`~/.config/autostart/`) |

Not Arch or KDE specific — works on any systemd-based distro (Ubuntu, Fedora, openSUSE, Debian, etc.) as long as the lenovolegionlinux driver is installed.

## Tested on

- **Lenovo Legion 5 Pro Gen 7** (BIOS JUCN66WW)
- AMD Radeon 680M (iGPU) + NVIDIA GeForce RTX 3070 Ti Laptop GPU
- KDE Plasma 6.6 on Wayland, kernel 6.18, Manjaro Linux

> **Note:** This machine requires `force=1` for the legion_laptop module and the `--donotexpecthwmon` flag for `legion_cli`. Other Legion models with full hwmon support may work without these workarounds — the commands would need adjusting in `main.py` and the sudoers/polkit config.

## Dependencies

- Python 3.8+
- PyQt6
  - Arch/Manjaro: `sudo pacman -S python-pyqt6`
  - Ubuntu/Debian: `sudo apt install python3-pyqt6`
  - Fedora: `sudo dnf install python3-qt6`
  - Or via pip: `pip install pyqt6`
- [lenovolegionlinux](https://github.com/johnfanv2/LenovoLegionLinux) driver (`legion_cli` must be in `$PATH`)
- polkit (`pkexec`)

## Installation

```bash
git clone https://github.com/pongsn/legion-gpu-mode-switcher.git
cd legion-gpu-mode-switcher
sudo bash install.sh
```

`install.sh` will:
1. Install the polkit policy to `/usr/share/polkit-1/actions/` (enables passwordless switching for the active session)
2. Install the app to `/usr/local/bin/legion-gpu-mode-switcher`
3. Install the autostart entry to `~/.config/autostart/` (starts on next login)

## Usage

```bash
legion-gpu-mode-switcher &
```

Right-click the tray icon to switch GPU mode. A reboot is required for any mode change to take effect — this is a hardware MUX limitation, same as on Windows.
