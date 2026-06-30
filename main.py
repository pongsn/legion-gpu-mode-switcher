#!/usr/bin/env python3
import sys
import os
import subprocess
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QPen
from PyQt6.QtCore import Qt, QTimer, QRect

MODE_LABELS = {
    'hybrid':  'Hybrid (iGPU + dGPU)',
    'dgpu':    'dGPU only',
    'unknown': 'Unknown',
}

SWITCH_LABELS = {
    'hybrid': 'Switch to Hybrid (iGPU + dGPU)',
    'dgpu':   'Switch to dGPU only',
}

AMD_RED  = QColor('#EF5350')
NV_GREEN = QColor('#66BB6A')
GREY     = QColor('#9E9E9E')
BADGE    = QColor('#FFA726')


_NVIDIA_DEVS = {'/dev/nvidia0', '/dev/nvidiactl', '/dev/nvidia-modeset', '/dev/nvidia-uvm'}

def get_dgpu_processes():
    """Return sorted list of (pid, name) for every process with an NVIDIA device open."""
    found = {}
    try:
        for entry in os.scandir('/proc'):
            if not entry.name.isdigit():
                continue
            pid = entry.name
            try:
                for fd_entry in os.scandir(f'/proc/{pid}/fd'):
                    try:
                        if os.readlink(fd_entry.path) in _NVIDIA_DEVS:
                            with open(f'/proc/{pid}/comm') as f:
                                found[pid] = f.read().strip()
                            break
                    except OSError:
                        pass
            except (PermissionError, FileNotFoundError):
                pass
    except Exception:
        pass
    return sorted(found.items(), key=lambda x: int(x[0]))


def get_active_gpu():
    """Returns 'dgpu' if any user process has /dev/nvidia0 open, else 'igpu'.
    runtime_status is unreliable here because nvidia-drm.modeset=1 keeps the
    PCI device active regardless of user-space usage."""
    try:
        r = subprocess.run(
            ['fuser', '/dev/nvidia0'],
            capture_output=True, timeout=3,
        )
        return 'dgpu' if r.returncode == 0 else 'igpu'
    except Exception:
        pass
    return 'igpu'


def get_mode():
    try:
        r = subprocess.run(
            ['legion_cli', '--donotexpecthwmon', 'hybrid-mode-status'],
            capture_output=True, text=True, timeout=5,
        )
        out = r.stdout + r.stderr
        if 'True' in out:
            return 'hybrid'
        if 'False' in out:
            return 'dgpu'
    except Exception:
        pass
    return 'unknown'


def switch_mode(target):
    cmd = 'hybrid-mode-enable' if target == 'hybrid' else 'hybrid-mode-disable'
    r = subprocess.run(
        ['pkexec', '/usr/bin/legion_cli', '--donotexpecthwmon', cmd],
        capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0


def make_icon(mode, pending=False, active_gpu='igpu'):
    size = 22
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    if mode == 'hybrid':
        c_left, c_right = AMD_RED, NV_GREEN
    elif mode == 'dgpu':
        c_left = c_right = NV_GREEN
    else:
        c_left = c_right = GREY

    def with_alpha(color, alpha):
        c = QColor(color); c.setAlpha(alpha); return c

    # ── Card body (landscape PCIe card) ────────────────────────
    card = QRect(1, 4, 20, 12)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(with_alpha(c_left, 200))
    p.save(); p.setClipRect(QRect(0, 0, 11, size))
    p.drawRoundedRect(card, 2, 2)
    p.restore()
    p.setBrush(with_alpha(c_right, 200))
    p.save(); p.setClipRect(QRect(11, 0, 11, size))
    p.drawRoundedRect(card, 2, 2)
    p.restore()

    # ── Two cooling fans ────────────────────────────────────────
    fan_r, fan_cy = 4, 10
    # In hybrid mode highlight the hub of whichever GPU is active
    active_fx = 16 if (mode == 'hybrid' and active_gpu == 'dgpu') else 6

    for fx in [6, 16]:
        is_active = (fx == active_fx and mode == 'hybrid')
        # Disc — tinted yellow for active fan, plain white otherwise
        disc = QColor(255, 220, 80, 140) if is_active else QColor(255, 255, 255, 140)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(disc)
        p.drawEllipse(fx - fan_r, fan_cy - fan_r, fan_r * 2, fan_r * 2)
        # Blade cross
        p.setPen(QPen(QColor(0, 0, 0, 110), 0.8))
        p.drawLine(fx, fan_cy - fan_r + 1, fx, fan_cy + fan_r - 1)
        p.drawLine(fx - fan_r + 1, fan_cy, fx + fan_r - 1, fan_cy)
        # Circle outline — bright yellow ring for active, darker for inactive
        if is_active:
            p.setPen(QPen(QColor(255, 230, 100, 230), 1.2))
        else:
            p.setPen(QPen(QColor(0, 0, 0, 130), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(fx - fan_r, fan_cy - fan_r, fan_r * 2, fan_r * 2)
        # Hub dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(fx - 1, fan_cy - 1, 2, 2)

    # ── Card outline ────────────────────────────────────────────
    p.setPen(QPen(QColor(0, 0, 0, 70), 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(card, 2, 2)

    # ── PCIe gold contact fingers ───────────────────────────────
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(200, 160, 50, 230))
    for tx in [3, 6, 9, 12, 15]:
        p.drawRect(tx, 16, 2, 3)

    if pending:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BADGE)
        p.drawEllipse(15, 0, 6, 6)

    p.end()
    return QIcon(px)


class GpuModeTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.active_mode = get_mode()
        self.pending_mode = None
        self.active_gpu = get_active_gpu() if self.active_mode == 'hybrid' else None
        self.app.setWindowIcon(make_icon(self.active_mode, active_gpu=self.active_gpu))
        self.tray = QSystemTrayIcon(make_icon(self.active_mode, active_gpu=self.active_gpu))
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(30_000)

        self.gpu_timer = QTimer()
        self.gpu_timer.timeout.connect(self._refresh_active_gpu)
        self.gpu_timer.start(5_000)

    def _build_menu(self):
        self.menu = QMenu()

        self.status_item = QAction()
        self.status_item.setEnabled(False)
        self.menu.addAction(self.status_item)
        self.menu.addSeparator()

        self.hybrid_action = QAction()
        self.hybrid_action.triggered.connect(lambda: self._request_switch('hybrid'))
        self.menu.addAction(self.hybrid_action)

        self.dgpu_action = QAction()
        self.dgpu_action.triggered.connect(lambda: self._request_switch('dgpu'))
        self.menu.addAction(self.dgpu_action)

        self.sep_dgpu_procs = self.menu.addSeparator()
        self.dgpu_procs_action = QAction('Show dGPU processes')
        self.dgpu_procs_action.triggered.connect(self._show_dgpu_processes)
        self.menu.addAction(self.dgpu_procs_action)

        self.sep_pending = self.menu.addSeparator()
        self.cancel_action = QAction()
        self.cancel_action.triggered.connect(self._cancel_switch)
        self.menu.addAction(self.cancel_action)

        self.reboot_action = QAction('Reboot now')
        self.reboot_action.triggered.connect(lambda: subprocess.run(['systemctl', 'reboot']))
        self.menu.addAction(self.reboot_action)

        self.menu.addSeparator()
        self.exit_action = QAction('Exit')
        self.exit_action.triggered.connect(self.app.quit)
        self.menu.addAction(self.exit_action)

        self._sync_ui()

    def _sync_ui(self):
        pending = self.pending_mode is not None
        active_label = MODE_LABELS[self.active_mode]

        if pending:
            pending_label = MODE_LABELS[self.pending_mode]
            self.status_item.setText(f'GPU mode: {active_label}')
            self.tray.setToolTip(f'GPU mode: {active_label} → {pending_label} (pending reboot)')
        else:
            self.status_item.setText(f'GPU mode: {active_label}')
            self.tray.setToolTip(f'GPU mode: {active_label}')

        icon = make_icon(self.active_mode, pending=pending, active_gpu=self.active_gpu)
        self.tray.setIcon(icon)
        self.app.setWindowIcon(icon)

        # Switch action labels and enabled state
        for key, action in [('hybrid', self.hybrid_action), ('dgpu', self.dgpu_action)]:
            if pending and key == self.pending_mode:
                action.setText(f'{MODE_LABELS[key]} (pending reboot)')
                action.setEnabled(False)
            elif pending:
                action.setText(SWITCH_LABELS[key])
                action.setEnabled(False)
            else:
                action.setText(SWITCH_LABELS[key])
                action.setEnabled(self.active_mode != key)

        dgpu_active = self.active_gpu == 'dgpu' or self.active_mode == 'dgpu'
        self.sep_dgpu_procs.setVisible(dgpu_active)
        self.dgpu_procs_action.setVisible(dgpu_active)

        self.sep_pending.setVisible(pending)
        self.cancel_action.setVisible(pending)
        self.reboot_action.setVisible(pending)
        if pending:
            self.cancel_action.setText(f'Cancel switch to {MODE_LABELS[self.pending_mode]}')

    def _show_dgpu_processes(self):
        procs = get_dgpu_processes()
        if procs:
            text = '\n'.join(f'{name}  (PID {pid})' for pid, name in procs)
        else:
            text = 'No processes currently using the dGPU.'
        QMessageBox.information(None, 'dGPU processes', text)

    def _refresh_active_gpu(self):
        if self.active_mode != 'hybrid':
            return
        gpu = get_active_gpu()
        if gpu != self.active_gpu:
            self.active_gpu = gpu
            self._sync_ui()

    def _refresh(self):
        mode = get_mode()
        if mode != self.active_mode:
            self.active_mode = mode
            self.active_gpu = get_active_gpu() if mode == 'hybrid' else None
            self.pending_mode = None
            self._sync_ui()

    def _request_switch(self, target):
        label = MODE_LABELS[target]
        if QMessageBox.question(
            None,
            'Switch GPU mode',
            f'Switch to <b>{label}</b>?<br><br>A reboot is required for the change to take effect.',
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Ok:
            return

        if not switch_mode(target):
            QMessageBox.warning(None, 'GPU mode', 'Failed to switch GPU mode.\nCheck polkit authentication.')
            return

        self.pending_mode = target
        self._sync_ui()

        self.tray.showMessage(
            'GPU mode switch pending',
            f'Will switch to {label} after reboot. Use the tray menu to cancel.',
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )

        if QMessageBox.question(
            None,
            'Reboot required',
            f'GPU mode will switch to <b>{label}</b> after reboot.<br><br>Reboot now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            subprocess.run(['systemctl', 'reboot'])

    def _cancel_switch(self):
        if not self.pending_mode:
            return
        if not switch_mode(self.active_mode):
            QMessageBox.warning(None, 'GPU mode', 'Failed to revert GPU mode.\nCheck polkit authentication.')
            return
        self.pending_mode = None
        self._sync_ui()
        self.tray.showMessage(
            'GPU mode switch cancelled',
            'No changes will be applied on reboot.',
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    def run(self):
        sys.exit(self.app.exec())


if __name__ == '__main__':
    GpuModeTray().run()
