import os
import sys
from dotenv import set_key, load_dotenv
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QMessageBox, QTabWidget, QWidget, QSizePolicy, QSpacerItem, QToolButton, QStyle, QFileDialog,
    QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QCoreApplication, QProcess, pyqtSignal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow
from utils import ConfigManager

load_dotenv()

class SettingsWindow(BaseWindow):
    settings_closed = pyqtSignal()
    settings_saved = pyqtSignal()
    listening_pause_request = pyqtSignal()
    listening_resume_request = pyqtSignal()

    def __init__(self):
        """Initialize the settings window."""
        super().__init__('Settings', 700, 700)
        self.schema = ConfigManager.get_schema()
        self.init_settings_ui()
        self._original_values = self._snapshot_current_values()
        self._apply_styling()
        # Allow resizing (override BaseWindow fixed size)
        self.setMinimumSize(780, 760)
        self.setMaximumSize(16777215, 16777215)
        self.resize(820, 800)

    def init_settings_ui(self):
        """Initialize the settings user interface."""
        # Header
        header = QLabel('Settings')
        header.setObjectName('SettingsHeader')
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.main_layout.addWidget(header)

        # Tabs (each made scrollable)
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self.create_tabs()

        # Footer actions
        self.create_buttons()

        # Connect the use_api checkbox state change
        self.use_api_checkbox = self.findChild(QCheckBox, 'model_options_use_api_input')
        if self.use_api_checkbox:
            self.use_api_checkbox.stateChanged.connect(lambda: self.toggle_api_local_options(self.use_api_checkbox.isChecked()))
            self.toggle_api_local_options(self.use_api_checkbox.isChecked())

    def create_tabs(self):
        """Create tabs for each category in the schema (scrollable)."""
        from PyQt5.QtWidgets import QScrollArea
        for category, settings in self.schema.items():
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(12, 12, 12, 12)
            container_layout.setSpacing(12)

            # Build content
            self.create_settings_widgets(container_layout, category, settings)
            container_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

            # Wrap in scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            # Avoid horizontal scrolling; keep content within width
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(container)
            tab_title = 'Gaming and Performance' if category == 'performance' else category.replace('_', ' ').capitalize()
            self.tabs.addTab(scroll, tab_title)

    def create_settings_widgets(self, layout, category, settings):
        """Create widgets for each setting in a category, grouped per sub-category."""
        from PyQt5.QtWidgets import QGroupBox, QVBoxLayout
        for sub_category, sub_settings in settings.items():
            # Flat (no subcategory) single value
            if isinstance(sub_settings, dict) and 'value' in sub_settings:
                self.add_setting_widget(layout, sub_category, sub_settings, category)
                continue

            # Grouped subcategory
            group_title = sub_category.replace('_', ' ').capitalize()
            group = QGroupBox(group_title)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 12, 12, 12)
            group_layout.setSpacing(8)

            for key, meta in sub_settings.items():
                self.add_setting_widget(group_layout, key, meta, category, sub_category)

            layout.addWidget(group)

        # Add running process selectors and list previews in performance tab
        if category == 'performance':
            layout.addLayout(self._build_process_selector())
            layout.addSpacing(8)
            layout.addLayout(self._build_process_lists_preview())

    def create_buttons(self):
        """Create reset and save buttons in a bottom action bar."""
        actions = QHBoxLayout()
        actions.addStretch(1)
        reset_button = QPushButton('Reset to saved settings')
        reset_button.setObjectName('ResetButton')
        reset_button.clicked.connect(self.reset_settings)
        actions.addWidget(reset_button)

        save_button = QPushButton('Save')
        save_button.setObjectName('SaveButton')
        save_button.clicked.connect(self.save_settings)
        actions.addWidget(save_button)
        self.main_layout.addLayout(actions)

    def add_setting_widget(self, layout, key, meta, category, sub_category=None):
        """Add a setting widget to the layout."""
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(f"{key.replace('_', ' ').capitalize()}")
        label.setObjectName('FieldLabel')
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        widget = self.create_widget_for_type(key, meta, category, sub_category)
        if not widget:
            return

        description = meta.get('description', '')
        help_button = self.create_help_button(description)
        help_button.setObjectName('HelpButton')

        row.addWidget(label, 2)
        if isinstance(widget, QWidget):
            row.addWidget(widget, 5)
        else:
            row.addLayout(widget, 5)
        row.addWidget(help_button, 0)
        layout.addLayout(row)
        # Hover tooltips on label and widget for quicker discovery
        if description:
            label.setToolTip(description)
            if isinstance(widget, QWidget):
                widget.setToolTip(description)
            else:
                try:
                    inner = widget.itemAt(0).widget()
                    if isinstance(inner, QWidget):
                        inner.setToolTip(description)
                except Exception:
                    pass

    def _build_process_selector(self):
        from PyQt5.QtWidgets import QListWidget, QAbstractItemView, QLineEdit
        wrapper = QHBoxLayout()
        wrapper.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(6)
        right = QVBoxLayout()
        right.setSpacing(6)

        left.addWidget(QLabel('Running processes'))
        search_box = QLineEdit()
        search_box.setPlaceholderText('Search processes...')
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
                self._all_running_procs = []
                for p in psutil.process_iter(['name']):
                    name = (p.info.get('name') or '').strip()
                    if not name:
                        continue
                    nl = name.lower()
                    if nl in seen:
                        continue
                    seen.add(nl)
                    self._all_running_procs.append(name)
                # Apply current filter
                apply_filter(search_box.text())
            except Exception:
                QMessageBox.warning(self, 'Processes', 'Unable to enumerate running processes.')

        def apply_filter(text: str):
            proc_list.clear()
            if not hasattr(self, '_all_running_procs'):
                return
            needle = (text or '').lower().strip()
            ignore = ConfigManager.get_config_value('performance', 'ignore_processes') or []
            force = ConfigManager.get_config_value('performance', 'force_game_processes') or []
            excluded = set([x.lower() for x in ignore] + [x.lower() for x in force])
            for name in sorted(self._all_running_procs, key=lambda s: s.lower()):
                if name.lower() in excluded:
                    continue
                if not needle or needle in name.lower():
                    proc_list.addItem(name)

        search_box.textChanged.connect(apply_filter)
        # Expose filter and search box so other panels can update the running list dynamically
        self._proc_apply_filter = apply_filter
        self._proc_search_box = search_box

        buttons_row = QHBoxLayout()
        btn_refresh = QPushButton('Refresh')
        btn_refresh.clicked.connect(refresh_processes)
        buttons_row.addWidget(btn_refresh)
        left.addLayout(buttons_row)

        quick_add_label = QLabel('Quick add to lists')
        right.addWidget(quick_add_label)
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
                # Merge with existing config list
                current = list(ConfigManager.get_config_value('performance', target_key) or [])
                current_lc = set([str(x).lower() for x in current])
                for name in selected:
                    nl = name.lower()
                    if nl not in current_lc:
                        current.append(name)
                        current_lc.add(nl)
                # Enforce exclusivity across lists
                other_key = 'force_game_processes' if target_key == 'ignore_processes' else 'ignore_processes'
                other = list(ConfigManager.get_config_value('performance', other_key) or [])
                other = [x for x in other if x.lower() not in [s.lower() for s in selected]]
                # Save back to config object only (persist on Save)
                ConfigManager.set_config_value(current, 'performance', target_key)
                ConfigManager.set_config_value(other, 'performance', other_key)
                friendly = 'Never enter Gaming Mode' if target_key == 'ignore_processes' else 'Always enter Gaming Mode'
                QMessageBox.information(self, 'Added', f'Added {len(selected)} process(es) to {friendly}. Changes will be saved on Save.')
                # Refresh lists and remove from running list view
                if hasattr(self, '_refresh_perf_lists') and callable(self._refresh_perf_lists):
                    try:
                        self._refresh_perf_lists()
                    except Exception:
                        pass
                apply_filter(search_box.text())
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not add selected items.\n{e}')

        btn_add_ignore.clicked.connect(lambda: add_selected('ignore_processes'))
        btn_add_force.clicked.connect(lambda: add_selected('force_game_processes'))

        wrapper.addLayout(left, 3)
        wrapper.addSpacing(12)
        wrapper.addLayout(right, 2)
        refresh_processes()
        return wrapper

    def _build_process_lists_preview(self):
        from PyQt5.QtWidgets import QListWidget, QAbstractItemView
        container = QHBoxLayout()
        container.setSpacing(12)
        # Left (Never enter Gaming Mode)
        ignore_col = QVBoxLayout()
        ignore_col.setSpacing(6)
        # Right (Always enter Gaming Mode)
        force_col = QVBoxLayout()
        force_col.setSpacing(6)
        # Middle controls
        middle_col = QVBoxLayout()
        middle_col.setSpacing(12)

        ignore_label = QLabel("Never enter Gaming Mode for these processes (ignore list)")
        force_label = QLabel("Always enter Gaming Mode for these processes (treat as game)")
        ignore_label.setWordWrap(True)
        force_label.setWordWrap(True)
        ignore_list = QListWidget()
        force_list = QListWidget()
        ignore_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        force_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        ignore_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        force_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        def refresh_lists():
            ignore = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'ignore_processes') or [])]
            force = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'force_game_processes') or [])]
            ignore_list.clear()
            force_list.clear()
            for name in ignore:
                ignore_list.addItem(name)
            for name in force:
                force_list.addItem(name)
        # Expose refresher for use by other handlers
        self._refresh_perf_lists = refresh_lists

        # Per-list controls
        btn_refresh_ignore = QPushButton('Refresh')
        btn_remove_ignore = QPushButton('Remove selected')
        btn_refresh_force = QPushButton('Refresh')
        btn_remove_force = QPushButton('Remove selected')
        # Middle move button toggles direction based on which list has selection
        btn_move_toggle = QPushButton('Move selected ↔')

        def remove_selected(target_key, list_widget):
            try:
                selected = [i.text() for i in list_widget.selectedItems()]
                if not selected:
                    return
                current = ConfigManager.get_config_value('performance', target_key) or []
                current_lc = [str(x).lower() for x in current]
                remaining = [x for x in current if x.lower() not in [s.lower() for s in selected]]
                if len(remaining) != len(current):
                    ConfigManager.set_config_value(remaining, 'performance', target_key)
                    # No dialog spam; lists update visually
                    refresh_lists()
                    # Also repopulate the running processes list intelligently
                    if hasattr(self, '_proc_apply_filter') and hasattr(self, '_proc_search_box'):
                        try:
                            self._proc_apply_filter(self._proc_search_box.text())
                        except Exception:
                            pass
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not remove selected items.\n{e}')

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
                    # Move from ignore -> force
                    ignore = [x for x in ignore if x.lower() not in [s.lower() for s in sel_ignore]]
                    for name in sel_ignore:
                        if name.lower() not in force_lc:
                            force.append(name)
                            force_lc.add(name.lower())
                            changed = True
                if sel_force:
                    # Move from force -> ignore
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
                    if hasattr(self, '_proc_apply_filter') and hasattr(self, '_proc_search_box'):
                        try:
                            self._proc_apply_filter(self._proc_search_box.text())
                        except Exception:
                            pass
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not move selected items.\n{e}')

        btn_refresh_ignore.clicked.connect(refresh_lists)
        btn_remove_ignore.clicked.connect(lambda: remove_selected('ignore_processes', ignore_list))
        btn_refresh_force.clicked.connect(refresh_lists)
        btn_remove_force.clicked.connect(lambda: remove_selected('force_game_processes', force_list))
        btn_move_toggle.clicked.connect(move_toggle)

        # Assemble columns
        ignore_controls = QHBoxLayout()
        ignore_controls.setSpacing(8)
        ignore_controls.addWidget(btn_refresh_ignore)
        ignore_controls.addWidget(btn_remove_ignore)
        ignore_col.addWidget(ignore_label)
        ignore_col.addWidget(ignore_list)
        ignore_col.addLayout(ignore_controls)

        force_controls = QHBoxLayout()
        force_controls.setSpacing(8)
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

    def create_widget_for_type(self, key, meta, category, sub_category):
        """Create a widget based on the meta type."""
        meta_type = meta.get('type')
        current_value = self.get_config_value(category, sub_category, key, meta)

        if key == 'activation_key' and meta_type == 'str':
            return self.create_activation_key_input(current_value)
        if key == 'sound_device':
            return self.create_sound_device_input(current_value)
        if meta_type == 'bool':
            return self.create_checkbox(current_value, key)
        elif meta_type == 'str' and 'options' in meta:
            return self.create_combobox(current_value, meta['options'])
        elif meta_type == 'str':
            return self.create_line_edit(current_value, key)
        elif meta_type in ['int', 'float']:
            return self.create_numeric_input(current_value, meta_type)
        return None

    def create_checkbox(self, value, key):
        widget = QCheckBox()
        widget.setChecked(value)
        if key == 'use_api':
            widget.setObjectName('model_options_use_api_input')
        return widget

    def create_combobox(self, value, options):
        widget = QComboBox()
        widget.addItems(options)
        widget.setCurrentText(value)
        return widget

    def create_line_edit(self, value, key=None):
        widget = QLineEdit(value)
        if key == 'api_key':
            widget.setEchoMode(QLineEdit.Password)
            widget.setText(os.getenv('OPENAI_API_KEY') or value)
        elif key == 'model_path':
            layout = QHBoxLayout()
            layout.addWidget(widget)
            browse_button = QPushButton('Browse')
            browse_button.clicked.connect(lambda: self.browse_model_path(widget))
            layout.addWidget(browse_button)
            layout.setContentsMargins(0, 0, 0, 0)
            container = QWidget()
            container.setLayout(layout)
            return container
        return widget

    def create_activation_key_input(self, value: str):
        line = QLineEdit(value or '')
        line.setReadOnly(True)
        set_btn = QPushButton('Set')
        def on_set():
            self.listening_pause_request.emit()
            combo = self.capture_activation_combo()
            if combo:
                line.setText(combo)
            self.listening_resume_request.emit()
        set_btn.clicked.connect(on_set)
        layout = QHBoxLayout()
        layout.addWidget(line)
        layout.addWidget(set_btn)
        layout.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        container.setLayout(layout)
        return container

    def create_sound_device_input(self, value: str | None):
        line = QLineEdit(str(value) if value is not None else '')
        select_btn = QPushButton('Select')
        def on_select():
            try:
                idx = self.select_sound_device_dialog()
            except Exception as e:
                QMessageBox.warning(self, 'Sound devices', f'Unable to query audio devices.\n{e}')
                return
            if idx is not None:
                line.setText(str(idx))
        select_btn.clicked.connect(on_select)
        layout = QHBoxLayout()
        layout.addWidget(line)
        layout.addWidget(select_btn)
        layout.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        container.setLayout(layout)
        return container

    def capture_activation_combo(self) -> str:
        dialog = KeyCaptureDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.combo_string()
        return ''

    def select_sound_device_dialog(self) -> int | None:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception as e:
            raise e

        entries = [(None, "System default (Windows / OS default)")]
        for i, d in enumerate(devices):
            if d.get('max_input_channels', 0) > 0:
                api = hostapis[d['hostapi']]['name'] if isinstance(d.get('hostapi'), int) and d['hostapi'] < len(hostapis) else 'Unknown API'
                name = d.get('name', f'Device {i}')
                entries.append((i, f"{i}: {name} ({api})"))

        if not entries:
            QMessageBox.information(self, 'Sound devices', 'No input devices found.')
            return None

        dlg = QDialog(self)
        dlg.setWindowTitle('Select audio input device')
        dlg.setModal(True)
        dlg.setFixedSize(520, 360)
        v = QVBoxLayout(dlg)
        label = QLabel('Choose an input device for recording:')
        v.addWidget(label)
        from PyQt5.QtWidgets import QListWidget
        lst = QListWidget()
        for _, text in entries:
            lst.addItem(text)
        v.addWidget(lst)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted and lst.currentRow() >= 0:
            return entries[lst.currentRow()][0]
        return None

    def create_numeric_input(self, value, value_type):
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox
        if value_type == 'int':
            spin = QSpinBox()
            spin.setRange(-10_000_000, 10_000_000)
            spin.setValue(int(value))
            return spin
        else:
            dspin = QDoubleSpinBox()
            dspin.setDecimals(6)
            dspin.setSingleStep(0.001)
            dspin.setRange(-1000.0, 1000.0)
            dspin.setValue(float(value))
            return dspin

    def create_help_button(self, description):
        help_button = QToolButton()
        help_button.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxQuestion))
        help_button.setAutoRaise(True)
        help_button.setToolTip(description)
        help_button.setCursor(Qt.PointingHandCursor)
        help_button.setFocusPolicy(Qt.NoFocus)
        help_button.clicked.connect(lambda: self.show_description(description))
        return help_button

    def get_config_value(self, category, sub_category, key, meta):
        if sub_category:
            return ConfigManager.get_config_value(category, sub_category, key) or meta['value']
        return ConfigManager.get_config_value(category, key) or meta['value']

    def browse_model_path(self, widget):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Whisper Model File", "", "Model Files (*.bin);;All Files (*)")
        if file_path:
            widget.setText(file_path)

    def show_description(self, description):
        """Show a description dialog."""
        QMessageBox.information(self, 'Description', description)

    def save_settings(self):
        """Save the settings to the config file and .env file."""
        self.iterate_settings(self.save_setting)
        # Update original snapshot after saving
        self._original_values = self._snapshot_current_values()

        # Save the API key to the .env file
        api_key = ConfigManager.get_config_value('model_options', 'api', 'api_key') or ''
        set_key('.env', 'OPENAI_API_KEY', api_key)
        os.environ['OPENAI_API_KEY'] = api_key

        # Remove the API key from the config
        ConfigManager.set_config_value(None, 'model_options', 'api', 'api_key')

        ConfigManager.save_config()
        # Handle Windows startup toggle
        start_on_login = ConfigManager.get_config_value('misc', 'start_on_login') is True
        ConfigManager.ensure_windows_startup(start_on_login)
        QMessageBox.information(self, 'Settings Saved', 'Settings have been saved. The application will now restart.')
        self.settings_saved.emit()
        self.close()

    def save_setting(self, widget, category, sub_category, key, meta):
        value = self.get_widget_value_typed(widget, meta.get('type'))
        if sub_category:
            ConfigManager.set_config_value(value, category, sub_category, key)
        else:
            ConfigManager.set_config_value(value, category, key)

    def reset_settings(self):
        """Reset the settings to the saved values."""
        ConfigManager.reload_config()
        self.update_widgets_from_config()

    def update_widgets_from_config(self):
        """Update all widgets with values from the current configuration."""
        self.iterate_settings(self.update_widget_value)

    def update_widget_value(self, widget, category, sub_category, key, meta):
        """Update a single widget with the value from the configuration."""
        if sub_category:
            config_value = ConfigManager.get_config_value(category, sub_category, key)
        else:
            config_value = ConfigManager.get_config_value(category, key)

        self.set_widget_value(widget, config_value, meta.get('type'))

    def set_widget_value(self, widget, value, value_type):
        """Set the value of the widget."""
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox
        if isinstance(widget, QCheckBox):
            widget.setChecked(value)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value) if value is not None else '')
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value) if value is not None else 0)
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value) if value is not None else 0.0)
        elif isinstance(widget, QWidget) and widget.layout():
            # This is for the model_path widget
            line_edit = widget.layout().itemAt(0).widget()
            if isinstance(line_edit, QLineEdit):
                line_edit.setText(str(value) if value is not None else '')

    def get_widget_value_typed(self, widget, value_type):
        """Get the value of the widget with proper typing."""
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            return widget.currentText() or None
        elif isinstance(widget, QLineEdit):
            text = widget.text()
            if value_type == 'int':
                return int(text) if text else None
            elif value_type == 'float':
                return float(text) if text else None
            else:
                return text or None
        elif isinstance(widget, QSpinBox):
            return int(widget.value())
        elif isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        elif isinstance(widget, QWidget) and widget.layout():
            # This is for the model_path widget
            line_edit = widget.layout().itemAt(0).widget()
            if isinstance(line_edit, QLineEdit):
                return line_edit.text() or None
        return None

    def toggle_api_local_options(self, use_api):
        """Toggle visibility of API and local options."""
        self.iterate_settings(lambda w, c, s, k, m: self.toggle_widget_visibility(w, c, s, k, use_api))

    def toggle_widget_visibility(self, widget, category, sub_category, key, use_api):
        if sub_category in ['api', 'local']:
            widget.setVisible(use_api if sub_category == 'api' else not use_api)
            
            # Also toggle visibility of the corresponding label and help button
            label = self.findChild(QLabel, f"{category}_{sub_category}_{key}_label")
            help_button = self.findChild(QToolButton, f"{category}_{sub_category}_{key}_help")
            
            if label:
                label.setVisible(use_api if sub_category == 'api' else not use_api)
            if help_button:
                help_button.setVisible(use_api if sub_category == 'api' else not use_api)


    def iterate_settings(self, func):
        """Iterate over all settings and apply a function to each."""
        for category, settings in self.schema.items():
            for sub_category, sub_settings in settings.items():
                if isinstance(sub_settings, dict) and 'value' in sub_settings:
                    widget = self.findChild(QWidget, f"{category}_{sub_category}_input")
                    if widget:
                        func(widget, category, None, sub_category, sub_settings)
                else:
                    for key, meta in sub_settings.items():
                        widget = self.findChild(QWidget, f"{category}_{sub_category}_{key}_input")
                        if widget:
                            func(widget, category, sub_category, key, meta)

    def closeEvent(self, event):
        """Prompt only if there are unsaved changes; otherwise just close the window."""
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                'Close without saving?',
                    'Close settings without saving changes?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
        )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        # Revert UI to last saved config on close
        ConfigManager.reload_config()
        self.update_widgets_from_config()
        self.settings_closed.emit()
        event.accept()

    def _snapshot_current_values(self):
        values = {}
        def capture(widget, category, sub_category, key, meta):
            values[(category, sub_category, key)] = self.get_widget_value_typed(widget, meta.get('type'))
        self.iterate_settings(capture)
        return values

    def _has_unsaved_changes(self):
        current = self._snapshot_current_values()
        return any(current.get(k) != v for k, v in self._original_values.items())

    def _apply_styling(self):
        """Apply a more refined visual style to the Settings window."""
        self.setStyleSheet("""
            #SettingsHeader {
                font-size: 20px;
                font-weight: 600;
                padding: 4px 6px 12px 6px;
                color: #303030;
            }
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: -1px;
            }
            QTabBar::tab {
                padding: 6px 12px;
            }
            QGroupBox {
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #404040;
                font-weight: 600;
            }
            QLabel#FieldLabel {
                color: #404040;
            }
            QPushButton#SaveButton {
                background-color: #2d7dff;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton#SaveButton:hover {
                background-color: #1f67db;
            }
            QPushButton#ResetButton {
                padding: 6px 12px;
            }
            QToolButton#HelpButton {
                padding: 0 4px;
            }
        """)

class KeyCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Press desired activation combo')
        self.setModal(True)
        self.setFixedSize(420, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        v = QVBoxLayout(self)
        self.label = QLabel('Press keys (including modifiers). Release to confirm. Esc to cancel.')
        v.addWidget(self.label)
        self.combo_view = QLineEdit()
        self.combo_view.setReadOnly(True)
        v.addWidget(self.combo_view)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

        self.pressed = set()
        self.result_combo = ''

    def keyPressEvent(self, event):
        key = self._key_to_string(event)
        if key:
            self.pressed.add(key)
            self._update_view()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        # On last release, accept the combo
        key = self._key_to_string(event)
        if key and key in self.pressed:
            self.pressed.discard(key)
        if not self.pressed:
            # Build canonical combo order: CTRL+SHIFT+ALT+META+...+KEY
            mods = []
            others = []
            for k in list(self._last_combo):
                if k in ('CTRL', 'SHIFT', 'ALT', 'META'):
                    mods.append(k)
        else:
                    others.append(k)
        combo = '+'.join(mods + others)
        self.result_combo = combo
        self.accept()

    def _update_view(self):
        self._last_combo = sorted(self.pressed)
        self.combo_view.setText('+'.join(self._last_combo))

    def _key_to_string(self, event) -> str:
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Meta):
            return 'CTRL' if key == Qt.Key_Control else 'META'
        if key in (Qt.Key_Shift,):
            return 'SHIFT'
        if key in (Qt.Key_Alt,):
            return 'ALT'
        # Convert printable keys and function keys
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            return f'F{key - Qt.Key_F1 + 1}'
        text = event.text().upper()
        if text:
            # Normalize special characters
            mapping = {
                ' ': 'SPACE', '-': 'MINUS', '=': 'EQUALS', '[': 'LEFT_BRACKET', ']': 'RIGHT_BRACKET',
                ';': 'SEMICOLON', "'": 'QUOTE', '`': 'BACKQUOTE', '\\': 'BACKSLASH', ',': 'COMMA', '.': 'PERIOD', '/': 'SLASH'
            }
            return mapping.get(text, text)
        # Arrow and other special keys
        specials = {
            Qt.Key_Left: 'LEFT', Qt.Key_Right: 'RIGHT', Qt.Key_Up: 'UP', Qt.Key_Down: 'DOWN',
            Qt.Key_Return: 'ENTER', Qt.Key_Enter: 'ENTER', Qt.Key_Tab: 'TAB', Qt.Key_Backspace: 'BACKSPACE',
            Qt.Key_Escape: 'ESC', Qt.Key_Insert: 'INSERT', Qt.Key_Delete: 'DELETE', Qt.Key_Home: 'HOME',
            Qt.Key_End: 'END', Qt.Key_PageUp: 'PAGE_UP', Qt.Key_PageDown: 'PAGE_DOWN',
        }
        return specials.get(key, '')

    def combo_string(self) -> str:
        return self.result_combo
