from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox


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
        self._last_combo = []

    def keyPressEvent(self, event):
        key = self._key_to_string(event)
        if key:
            self.pressed.add(key)
            self._update_view()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        key = self._key_to_string(event)
        if key and key in self.pressed:
            self.pressed.discard(key)
        if not self.pressed:
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
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            return f'F{key - Qt.Key_F1 + 1}'
        text = event.text().upper()
        if text:
            mapping = {
                ' ': 'SPACE', '-': 'MINUS', '=': 'EQUALS', '[': 'LEFT_BRACKET', ']': 'RIGHT_BRACKET',
                ';': 'SEMICOLON', "'": 'QUOTE', '`': 'BACKQUOTE', '\\': 'BACKSLASH', ',': 'COMMA', '.': 'PERIOD', '/': 'SLASH'
            }
            return mapping.get(text, text)
        specials = {
            Qt.Key_Left: 'LEFT', Qt.Key_Right: 'RIGHT', Qt.Key_Up: 'UP', Qt.Key_Down: 'DOWN',
            Qt.Key_Return: 'ENTER', Qt.Key_Enter: 'ENTER', Qt.Key_Tab: 'TAB', Qt.Key_Backspace: 'BACKSPACE',
            Qt.Key_Escape: 'ESC', Qt.Key_Insert: 'INSERT', Qt.Key_Delete: 'DELETE', Qt.Key_Home: 'HOME',
            Qt.Key_End: 'END', Qt.Key_PageUp: 'PAGE_UP', Qt.Key_PageDown: 'PAGE_DOWN',
        }
        return specials.get(key, '')

    def combo_string(self) -> str:
        return self.result_combo



