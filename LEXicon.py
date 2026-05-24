import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QListWidgetItem, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QLabel, QFormLayout, QHBoxLayout, QVBoxLayout, QToolButton, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import pandas as pd


DB_PATH = "lexiko.db"
AUDIO_DIR = "audio"


@dataclass
class Entry:
    id: int
    key: str
    el: str
    en: str
    de: str
    ru: str
    ar: str
    es: str
    tr: str
    audio_el: str
    audio_en: str
    audio_de: str
    audio_ru: str
    audio_ar: str
    audio_es: str
    audio_tr: str
    category: str
    tags: str
    notes: str


class LexikoDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _ensure_column(self, cur, col_name, col_type="TEXT DEFAULT ''"):
        cols = [row["name"] for row in cur.execute("PRAGMA table_info(entries)").fetchall()]
        if col_name not in cols:
            cur.execute(f"ALTER TABLE entries ADD COLUMN {col_name} {col_type}")

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                el TEXT DEFAULT '',
                en TEXT DEFAULT '',
                de TEXT DEFAULT '',
                tr TEXT DEFAULT '',
                ar TEXT DEFAULT '',
                audio_el TEXT DEFAULT '',
                audio_en TEXT DEFAULT '',
                audio_de TEXT DEFAULT '',
                audio_tr TEXT DEFAULT '',
                audio_ar TEXT DEFAULT '',
                category TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                notes TEXT DEFAULT ''
            )
        """)

        self._ensure_column(cur, "ru")
        self._ensure_column(cur, "es")
        self._ensure_column(cur, "audio_ru")
        self._ensure_column(cur, "audio_es")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_entries_key ON entries(key)")
        self.conn.commit()

    def search(self, q: str) -> List[Entry]:
        q = (q or "").strip()
        cur = self.conn.cursor()
        if not q:
            cur.execute("SELECT * FROM entries ORDER BY key COLLATE NOCASE")
        else:
            like = f"%{q}%"
            cur.execute("""
                SELECT * FROM entries
                WHERE key LIKE ? OR el LIKE ? OR en LIKE ? OR de LIKE ? OR ru LIKE ?
                   OR ar LIKE ? OR es LIKE ? OR tr LIKE ? OR category LIKE ? OR tags LIKE ?
                ORDER BY key COLLATE NOCASE
            """, (like, like, like, like, like, like, like, like, like, like))
        rows = cur.fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_by_id(self, entry_id: int) -> Optional[Entry]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        row = cur.fetchone()
        return self._row_to_entry(row) if row else None

    def get_by_key(self, key: str) -> Optional[Entry]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM entries WHERE key = ?", (key,))
        row = cur.fetchone()
        return self._row_to_entry(row) if row else None

    def insert(self, data: Dict[str, str]) -> None:
        cur = self.conn.cursor()
        cols = ",".join(data.keys())
        qs = ",".join(["?"] * len(data))
        cur.execute(f"INSERT INTO entries ({cols}) VALUES ({qs})", tuple(data.values()))
        self.conn.commit()

    def update_by_key(self, key: str, data: Dict[str, str]) -> None:
        cur = self.conn.cursor()
        sets = ",".join([f"{k}=?" for k in data.keys()])
        cur.execute(f"UPDATE entries SET {sets} WHERE key = ?", tuple(data.values()) + (key,))
        self.conn.commit()

    def delete(self, entry_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_entry(r: sqlite3.Row) -> Entry:
        def safe_get(name: str) -> str:
            try:
                return r[name] or ""
            except Exception:
                return ""

        return Entry(
            id=int(r["id"]),
            key=safe_get("key"),
            el=safe_get("el"),
            en=safe_get("en"),
            de=safe_get("de"),
            ru=safe_get("ru"),
            ar=safe_get("ar"),
            es=safe_get("es"),
            tr=safe_get("tr"),
            audio_el=safe_get("audio_el"),
            audio_en=safe_get("audio_en"),
            audio_de=safe_get("audio_de"),
            audio_ru=safe_get("audio_ru"),
            audio_ar=safe_get("audio_ar"),
            audio_es=safe_get("audio_es"),
            audio_tr=safe_get("audio_tr"),
            category=safe_get("category"),
            tags=safe_get("tags"),
            notes=safe_get("notes"),
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Σχολικό Πολυλεξικό LEXicon (EL/EN/DE/RU/AR/ES/TR) Μπαλανίκα Ελένη -- V1.1.1 Copyright@2026")
        self.resize(1220, 720)

        os.makedirs(AUDIO_DIR, exist_ok=True)

        self.db = LexikoDB(DB_PATH)

        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        root = QWidget()
        self.setCentralWidget(root)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Αναζήτηση (key / οποιαδήποτε γλώσσα / κατηγορία / tags)...")
        self.search_input.textChanged.connect(self.refresh_list)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_select_item)

        self.btn_import = QPushButton("Import από Excel…")
        self.btn_import.clicked.connect(self.import_excel)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.search_input)
        left_layout.addWidget(self.list_widget)
        left_layout.addWidget(self.btn_import)

        self.key_input = QLineEdit()

        self.el_input = QLineEdit()
        self.en_input = QLineEdit()
        self.de_input = QLineEdit()
        self.ru_input = QLineEdit()
        self.ar_input = QLineEdit()
        self.es_input = QLineEdit()
        self.tr_input = QLineEdit()

        self.ar_input.setAlignment(Qt.AlignRight)

        ar_font = QFont()
        ar_font.setPointSize(12)
        self.ar_input.setFont(ar_font)
        self.ar_input.setLayoutDirection(Qt.RightToLeft)

        for field in [
            self.el_input, self.en_input, self.de_input, self.ru_input,
            self.ar_input, self.es_input, self.tr_input
        ]:
            field.setFixedHeight(30)

        self.category_input = QLineEdit()
        self.tags_input = QLineEdit()
        self.notes_input = QLineEdit()

        self.audio_el_input = QLineEdit()
        self.audio_en_input = QLineEdit()
        self.audio_de_input = QLineEdit()
        self.audio_ru_input = QLineEdit()
        self.audio_ar_input = QLineEdit()
        self.audio_es_input = QLineEdit()
        self.audio_tr_input = QLineEdit()

        form = QFormLayout()
        form.addRow("Key (μοναδικό):", self.key_input)

        form.addRow("Ελληνικά:", self._lang_row("🇬🇷", self.el_input, "el"))
        form.addRow("Αγγλικά:", self._lang_row("🇬🇧", self.en_input, "en"))
        form.addRow("Γερμανικά:", self._lang_row("🇩🇪", self.de_input, "de"))
        form.addRow("Ρώσικα:", self._lang_row("🇷🇺", self.ru_input, "ru"))
        form.addRow("Αραβικά:", self._lang_row("🇸🇦", self.ar_input, "ar"))
        form.addRow("Ισπανικά:", self._lang_row("🇪🇸", self.es_input, "es"))
        form.addRow("Τούρκικα:", self._lang_row("🇹🇷", self.tr_input, "tr"))

        form.addRow("Audio EL (όνομα mp3):", self.audio_el_input)
        form.addRow("Audio EN (όνομα mp3):", self.audio_en_input)
        form.addRow("Audio DE (όνομα mp3):", self.audio_de_input)
        form.addRow("Audio RU (όνομα mp3):", self.audio_ru_input)
        form.addRow("Audio AR (όνομα mp3):", self.audio_ar_input)
        form.addRow("Audio ES (όνομα mp3):", self.audio_es_input)
        form.addRow("Audio TR (όνομα mp3):", self.audio_tr_input)

        form.addRow("Κατηγορία:", self.category_input)
        form.addRow("Tags:", self.tags_input)
        form.addRow("Notes:", self.notes_input)

        self.btn_new = QPushButton("Νέα")
        self.btn_save = QPushButton("Αποθήκευση")
        self.btn_delete = QPushButton("Διαγραφή")
        self.btn_stop = QPushButton("Stop 🔇")

        self.btn_new.clicked.connect(self.new_entry)
        self.btn_save.clicked.connect(self.save_entry)
        self.btn_delete.clicked.connect(self.delete_entry)
        self.btn_stop.clicked.connect(self.stop_audio)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_stop)

        self.audio_hint = QLabel(f"MP3 φάκελος: ./{AUDIO_DIR}/  (βάλε εκεί τα αρχεία)")
        self.audio_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        right_layout = QVBoxLayout()
        right_layout.addLayout(form)
        right_layout.addSpacing(10)
        right_layout.addLayout(btn_row)
        right_layout.addWidget(self.audio_hint)

        credits = QLabel("Programmed by Glykiotis Konstantinos")
        credits.setAlignment(Qt.AlignRight)

        credits.setStyleSheet("""
        QLabel {
            color: #888888;
            font-size: 11px;
            font-style: italic;
            padding-right: 8px;
        }
        """)

        right_layout.addWidget(credits)

        right_layout.addStretch(1)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)
        root.setLayout(main_layout)

        self.current_entry_id: Optional[int] = None
        self.refresh_list()

    def _lang_row(self, flag_emoji: str, line_edit: QLineEdit, lang_code: str) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        flag = QLabel(flag_emoji)
        flag.setAlignment(Qt.AlignCenter)
        flag.setFixedWidth(28)

        line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn = QToolButton()
        btn.setText("🔊")
        btn.setToolTip(f"Play {lang_code.upper()}")
        btn.clicked.connect(lambda: self.play_lang(lang_code))
        btn.setFixedWidth(36)

        layout.addWidget(flag, 0, Qt.AlignVCenter)
        layout.addWidget(line_edit, 1, Qt.AlignVCenter)
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        return w

    def refresh_list(self):
        q = self.search_input.text()
        entries = self.db.search(q)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for idx, e in enumerate(entries, start=1):
            title = e.key
            if e.el.strip():
                title += f" — {e.el.strip()}"

            # Δείχνουμε καθαρή αρίθμηση λίστας αντί για το εσωτερικό DB id
            item = QListWidgetItem(f"{idx}. {title}")
            item.setData(Qt.UserRole, e.id)  # κρατάμε το πραγματικό id κρυφά
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        if self.list_widget.count() == 0:
            self.clear_form()

    def on_select_item(self):
        item = self.list_widget.currentItem()
        if not item:
            self.clear_form()
            return

        entry_id = item.data(Qt.UserRole)
        if entry_id is None:
            return

        entry = self.db.get_by_id(int(entry_id))
        if not entry:
            return

        self.current_entry_id = entry.id
        self.key_input.setText(entry.key)
        self.el_input.setText(entry.el)
        self.en_input.setText(entry.en)
        self.de_input.setText(entry.de)
        self.ru_input.setText(entry.ru)
        self.ar_input.setText(entry.ar)
        self.es_input.setText(entry.es)
        self.tr_input.setText(entry.tr)

        self.audio_el_input.setText(entry.audio_el)
        self.audio_en_input.setText(entry.audio_en)
        self.audio_de_input.setText(entry.audio_de)
        self.audio_ru_input.setText(entry.audio_ru)
        self.audio_ar_input.setText(entry.audio_ar)
        self.audio_es_input.setText(entry.audio_es)
        self.audio_tr_input.setText(entry.audio_tr)

        self.category_input.setText(entry.category)
        self.tags_input.setText(entry.tags)
        self.notes_input.setText(entry.notes)

    def clear_form(self):
        self.current_entry_id = None
        for w in [
            self.key_input, self.el_input, self.en_input, self.de_input, self.ru_input,
            self.ar_input, self.es_input, self.tr_input,
            self.audio_el_input, self.audio_en_input, self.audio_de_input, self.audio_ru_input,
            self.audio_ar_input, self.audio_es_input, self.audio_tr_input,
            self.category_input, self.tags_input, self.notes_input
        ]:
            w.clear()

    def new_entry(self):
        self.clear_form()
        QMessageBox.information(self, "Νέα εγγραφή", "Γράψε ένα μοναδικό key και πάτα 'Αποθήκευση'.")

    def save_entry(self):
        key = (self.key_input.text() or "").strip()
        if not key:
            QMessageBox.warning(self, "Σφάλμα", "Το 'key' είναι υποχρεωτικό.")
            return

        data = {
            "key": key,
            "el": (self.el_input.text() or "").strip(),
            "en": (self.en_input.text() or "").strip(),
            "de": (self.de_input.text() or "").strip(),
            "ru": (self.ru_input.text() or "").strip(),
            "ar": (self.ar_input.text() or "").strip(),
            "es": (self.es_input.text() or "").strip(),
            "tr": (self.tr_input.text() or "").strip(),
            "audio_el": (self.audio_el_input.text() or "").strip(),
            "audio_en": (self.audio_en_input.text() or "").strip(),
            "audio_de": (self.audio_de_input.text() or "").strip(),
            "audio_ru": (self.audio_ru_input.text() or "").strip(),
            "audio_ar": (self.audio_ar_input.text() or "").strip(),
            "audio_es": (self.audio_es_input.text() or "").strip(),
            "audio_tr": (self.audio_tr_input.text() or "").strip(),
            "category": (self.category_input.text() or "").strip(),
            "tags": (self.tags_input.text() or "").strip(),
            "notes": (self.notes_input.text() or "").strip(),
        }

        existing = self.db.get_by_key(key)
        try:
            if existing:
                data_no_key = {k: v for k, v in data.items() if k != "key"}
                self.db.update_by_key(key, data_no_key)
            else:
                self.db.insert(data)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Σφάλμα", "Υπάρχει ήδη άλλη εγγραφή με αυτό το key.")
            return

        self.refresh_list()
        QMessageBox.information(self, "OK", "Αποθηκεύτηκε!")

        refreshed = self.db.get_by_key(key)
        if refreshed:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.UserRole) == refreshed.id:
                    self.list_widget.setCurrentRow(i)
                    break

    def delete_entry(self):
        if self.current_entry_id is None:
            QMessageBox.information(self, "Δεν υπάρχει επιλογή", "Διάλεξε μια εγγραφή από τη λίστα.")
            return

        res = QMessageBox.question(
            self, "Διαγραφή", "Σίγουρα θέλεις να διαγράψεις αυτή τη λέξη;",
            QMessageBox.Yes | QMessageBox.No
        )
        if res != QMessageBox.Yes:
            return

        self.stop_audio()
        self.db.delete(self.current_entry_id)
        self.clear_form()
        self.refresh_list()

    def _audio_path(self, filename: str) -> Optional[str]:
        filename = (filename or "").strip()
        if not filename:
            return None
        if os.path.isabs(filename) and os.path.exists(filename):
            return filename
        candidate = os.path.join(AUDIO_DIR, filename)
        return candidate if os.path.exists(candidate) else None

    def play_lang(self, lang: str):
        mapping = {
            "el": self.audio_el_input.text(),
            "en": self.audio_en_input.text(),
            "de": self.audio_de_input.text(),
            "ru": self.audio_ru_input.text(),
            "ar": self.audio_ar_input.text(),
            "es": self.audio_es_input.text(),
            "tr": self.audio_tr_input.text(),
        }
        fname = mapping.get(lang, "")
        path = self._audio_path(fname)
        if not path:
            QMessageBox.information(
                self, "Δεν βρέθηκε ήχος",
                f"Δεν βρέθηκε αρχείο για {lang.upper()}.\n"
                f"Βάλε το mp3 στον φάκελο ./{AUDIO_DIR}/ και γράψε το όνομά του στο αντίστοιχο πεδίο audio."
            )
            return
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        self.player.play()

    def stop_audio(self):
        self.player.stop()

    def import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Διάλεξε Excel", "", "Excel (*.xlsx)")
        if not path:
            return

        try:
            df = pd.read_excel(path, sheet_name="Λέξεις")
        except Exception as e:
            QMessageBox.warning(self, "Σφάλμα", f"Δεν μπόρεσα να διαβάσω το Excel.\n{e}")
            return

        cols = {str(c).strip(): c for c in df.columns}
        if "key" not in cols:
            QMessageBox.warning(self, "Σφάλμα", "Λείπει η στήλη 'key' στο φύλλο 'Λέξεις'.")
            return

        allowed = {
            "key", "el", "en", "de", "ru", "ar", "es", "tr",
            "audio_el", "audio_en", "audio_de", "audio_ru", "audio_ar", "audio_es", "audio_tr",
            "category", "tags", "notes"
        }

        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        for _, row in df.iterrows():
            key = str(row.get(cols["key"], "")).strip()
            if not key or key.lower() == "nan":
                skipped += 1
                continue

            data = {}
            for k in allowed:
                if k in cols:
                    val = row.get(cols[k], "")
                    if val is None:
                        val = ""
                    val = str(val).strip()
                    if val.lower() == "nan":
                        val = ""
                    data[k] = val

            try:
                existing = self.db.get_by_key(key)
                if existing:
                    data_no_key = {k: v for k, v in data.items() if k != "key"}
                    self.db.update_by_key(key, data_no_key)
                    updated += 1
                else:
                    self.db.insert(data)
                    inserted += 1
            except Exception:
                errors += 1

        self.refresh_list()
        QMessageBox.information(
            self,
            "Import ολοκληρώθηκε",
            f"Νέα: {inserted}\nUpdate: {updated}\nΠαραλείφθηκαν (κενό key): {skipped}\nΣφάλματα: {errors}"
        )


if __name__ == "__main__":
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
