import os
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QAbstractItemView,
    QPushButton, QSizePolicy, QMessageBox
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import ConfigManager


def build_performance_widget(parent) -> QWidget:
    """Build the Gaming and Performance tab content as a single widget."""
    root = QWidget()
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(12)

    # Running processes selector
    selector = _build_process_selector(parent)
    root_layout.addLayout(selector)

    # Lists preview and controls
    lists = _build_process_lists_preview(parent)
    root_layout.addLayout(lists)

    return root


def _build_process_selector(parent):
    from PyQt5.QtWidgets import QHBoxLayout
    wrapper = QHBoxLayout()
    wrapper.setSpacing(12)
    left = QVBoxLayout(); left.setSpacing(6)
    right = QVBoxLayout(); right.setSpacing(6)

    left.addWidget(QLabel('Running processes'))
    search_box = QLineEdit(); search_box.setPlaceholderText('Search processes...')
    left.addWidget(search_box)

    proc_list = QListWidget()
    proc_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    proc_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    left.addWidget(proc_list)

    def refresh_processes():
        try:
            import psutil
            proc_list.clear()
            seen = set()
            parent._all_running_procs = []
            for p in psutil.process_iter(['name']):
                name = (p.info.get('name') or '').strip()
                if not name:
                    continue
                nl = name.lower()
                if nl in seen:
                    continue
                seen.add(nl)
                parent._all_running_procs.append(name)
            apply_filter(search_box.text())
        except Exception:
            QMessageBox.warning(parent, 'Processes', 'Unable to enumerate running processes.')

    def apply_filter(text: str):
        proc_list.clear()
        if not hasattr(parent, '_all_running_procs'):
            return
        needle = (text or '').lower().strip()
        ignore = ConfigManager.get_config_value('performance', 'ignore_processes') or []
        force = ConfigManager.get_config_value('performance', 'force_game_processes') or []
        excluded = set([x.lower() for x in ignore] + [x.lower() for x in force])
        for name in sorted(getattr(parent, '_all_running_procs', []), key=lambda s: s.lower()):
            if name.lower() in excluded:
                continue
            if not needle or needle in name.lower():
                proc_list.addItem(name)

    search_box.textChanged.connect(apply_filter)
    parent._proc_apply_filter = apply_filter
    parent._proc_search_box = search_box

    buttons_row = QHBoxLayout()
    btn_refresh = QPushButton('Refresh')
    btn_refresh.clicked.connect(refresh_processes)
    buttons_row.addWidget(btn_refresh)
    left.addLayout(buttons_row)

    right.addWidget(QLabel('Quick add to lists'))
    btn_add_ignore = QPushButton('Add selected to Never enter Gaming Mode')
    btn_add_ignore.setToolTip('These apps will not enter Gaming Mode (hotkey/model not affected).')
    btn_add_force = QPushButton('Add selected to Always enter Gaming Mode')
    btn_add_force.setToolTip('These apps will always be treated as games and enter Gaming Mode.')
    right.addWidget(btn_add_ignore)
    right.addWidget(btn_add_force)

    def add_selected(target_key):
        try:
            selected = [i.text() for i in proc_list.selectedItems()]
            if not selected:
                return
            current = list(ConfigManager.get_config_value('performance', target_key) or [])
            current_lc = set([str(x).lower() for x in current])
            for name in selected:
                nl = name.lower()
                if nl not in current_lc:
                    current.append(name)
                    current_lc.add(nl)
            other_key = 'force_game_processes' if target_key == 'ignore_processes' else 'ignore_processes'
            other = list(ConfigManager.get_config_value('performance', other_key) or [])
            other = [x for x in other if x.lower() not in [s.lower() for s in selected]]
            ConfigManager.set_config_value(current, 'performance', target_key)
            ConfigManager.set_config_value(other, 'performance', other_key)
            if hasattr(parent, '_refresh_perf_lists') and callable(parent._refresh_perf_lists):
                try:
                    parent._refresh_perf_lists()
                except Exception:
                    pass
            apply_filter(search_box.text())
        except Exception as e:
            QMessageBox.warning(parent, 'Error', f'Could not add selected items.\n{e}')

    btn_add_ignore.clicked.connect(lambda: add_selected('ignore_processes'))
    btn_add_force.clicked.connect(lambda: add_selected('force_game_processes'))

    wrapper.addLayout(left, 3)
    wrapper.addSpacing(12)
    wrapper.addLayout(right, 2)
    refresh_processes()
    return wrapper


def _build_process_lists_preview(parent):
    from PyQt5.QtWidgets import QHBoxLayout
    container = QHBoxLayout(); container.setSpacing(12)
    ignore_col = QVBoxLayout(); ignore_col.setSpacing(6)
    force_col = QVBoxLayout(); force_col.setSpacing(6)
    middle_col = QVBoxLayout(); middle_col.setSpacing(12)

    ignore_label = QLabel("Never enter Gaming Mode for these processes (ignore list)"); ignore_label.setWordWrap(True)
    force_label = QLabel("Always enter Gaming Mode for these processes (treat as game)"); force_label.setWordWrap(True)
    ignore_list = QListWidget(); force_list = QListWidget()
    for lst in (ignore_list, force_list):
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lst.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def refresh_lists():
        ignore = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'ignore_processes') or [])]
        force = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'force_game_processes') or [])]
        ignore_list.clear(); force_list.clear()
        for name in ignore:
            ignore_list.addItem(name)
        for name in force:
            force_list.addItem(name)
    parent._refresh_perf_lists = refresh_lists

    btn_refresh_ignore = QPushButton('Refresh')
    btn_remove_ignore = QPushButton('Remove selected')
    btn_refresh_force = QPushButton('Refresh')
    btn_remove_force = QPushButton('Remove selected')
    btn_move_toggle = QPushButton('Move selected ↔')

    def remove_selected(target_key, list_widget):
        try:
            selected = [i.text() for i in list_widget.selectedItems()]
            if not selected:
                return
            current = ConfigManager.get_config_value('performance', target_key) or []
            remaining = [x for x in current if x.lower() not in [s.lower() for s in selected]]
            if len(remaining) != len(current):
                ConfigManager.set_config_value(remaining, 'performance', target_key)
                refresh_lists()
                if hasattr(parent, '_proc_apply_filter') and hasattr(parent, '_proc_search_box'):
                    try:
                        parent._proc_apply_filter(parent._proc_search_box.text())
                    except Exception:
                        pass
        except Exception as e:
            QMessageBox.warning(parent, 'Error', f'Could not remove selected items.\n{e}')

    def move_toggle():
        try:
            sel_ignore = [i.text() for i in ignore_list.selectedItems()]
            sel_force = [i.text() for i in force_list.selectedItems()]
            ignore = ConfigManager.get_config_value('performance', 'ignore_processes') or []
            force = ConfigManager.get_config_value('performance', 'force_game_processes') or []
            ignore_lc = set([x.lower() for x in ignore])
            force_lc = set([x.lower() for x in force])
            changed = False
            if sel_ignore:
                ignore = [x for x in ignore if x.lower() not in [s.lower() for s in sel_ignore]]
                for name in sel_ignore:
                    if name.lower() not in force_lc:
                        force.append(name)
                        force_lc.add(name.lower())
                        changed = True
            if sel_force:
                force = [x for x in force if x.lower() not in [s.lower() for s in sel_force]]
                for name in sel_force:
                    if name.lower() not in ignore_lc:
                        ignore.append(name)
                        ignore_lc.add(name.lower())
                        changed = True
            if changed:
                ConfigManager.set_config_value(ignore, 'performance', 'ignore_processes')
                ConfigManager.set_config_value(force, 'performance', 'force_game_processes')
                refresh_lists()
                if hasattr(parent, '_proc_apply_filter') and hasattr(parent, '_proc_search_box'):
                    try:
                        parent._proc_apply_filter(parent._proc_search_box.text())
                    except Exception:
                        pass
        except Exception as e:
            QMessageBox.warning(parent, 'Error', f'Could not move selected items.\n{e}')

    btn_refresh_ignore.clicked.connect(refresh_lists)
    btn_remove_ignore.clicked.connect(lambda: remove_selected('ignore_processes', ignore_list))
    btn_refresh_force.clicked.connect(refresh_lists)
    btn_remove_force.clicked.connect(lambda: remove_selected('force_game_processes', force_list))
    btn_move_toggle.clicked.connect(move_toggle)

    ignore_controls = QHBoxLayout(); ignore_controls.setSpacing(8)
    ignore_controls.addWidget(btn_refresh_ignore)
    ignore_controls.addWidget(btn_remove_ignore)
    ignore_col.addWidget(ignore_label)
    ignore_col.addWidget(ignore_list)
    ignore_col.addLayout(ignore_controls)

    force_controls = QHBoxLayout(); force_controls.setSpacing(8)
    force_controls.addWidget(btn_refresh_force)
    force_controls.addWidget(btn_remove_force)
    force_col.addWidget(force_label)
    force_col.addWidget(force_list)
    force_col.addLayout(force_controls)

    middle_col.addStretch(1)
    middle_col.addWidget(btn_move_toggle)
    middle_col.addStretch(1)

    container.addLayout(ignore_col, 1)
    container.addLayout(middle_col)
    container.addLayout(force_col, 1)
    refresh_lists()
    return container



