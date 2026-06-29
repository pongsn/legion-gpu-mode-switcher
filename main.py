#!/usr/bin/env python3
import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QPen
from PyQt6.QtCore import Qt, QTimer, QRect

MODE_LABELS = {
    'hybrid':  'Hybrid (AMD + NVIDIA)',
    'dgpu':    'NVIDIA only',
    'unknown': 'Unknown',
}

SWITCH_LABELS = {
    'hybrid': 'Switch to Hybrid (AMD + NVIDIA)',
    'dgpu':   'Switch to NVIDIA only',
}

AMD_RED  = QColor('#EF5350')
NV_GREEN = QColor('#66BB6A')
GREY     = QColor('#9E9E9E')
BADGE    = QColor('#FFA726')


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


def _draw_chip(painter, color, clip=None):
    if clip:
        painter.save()
        painter.setClipRect(clip)
    pen = QPen(color, 1.5, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    # Body
    painter.drawRoundedRect(5, 5, 12, 12, 2, 2)
    # Left pins
    painter.drawRect(2, 8, 3, 2)
    painter.drawRect(2, 12, 3, 2)
    # Right pins
    painter.drawRect(17, 8, 3, 2)
    painter.drawRect(17, 12, 3, 2)
    # Top pins
    painter.drawRect(8, 2, 2, 3)
    painter.drawRect(12, 2, 2, 3)
    # Bottom pins
    painter.drawRect(8, 17, 2, 3)
    painter.drawRect(12, 17, 2, 3)
    if clip:
        painter.restore()


def make_icon(mode, pending=False):
    size = 22
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    if mode == 'hybrid':
        _draw_chip(p, AMD_RED,  QRect(0, 0, 11, size))
        _draw_chip(p, NV_GREEN, QRect(11, 0, 11, size))
    elif mode == 'dgpu':
        _draw_chip(p, NV_GREEN)
    else:
        _draw_chip(p, GREY)

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
        self.tray = QSystemTrayIcon(make_icon(self.active_mode))
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(30_000)

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

        self.tray.setIcon(make_icon(self.active_mode, pending=pending))

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

        self.sep_pending.setVisible(pending)
        self.cancel_action.setVisible(pending)
        self.reboot_action.setVisible(pending)
        if pending:
            self.cancel_action.setText(f'Cancel switch to {MODE_LABELS[self.pending_mode]}')

    def _refresh(self):
        mode = get_mode()
        if mode != self.active_mode:
            self.active_mode = mode
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
