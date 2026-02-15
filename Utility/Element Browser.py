import os
import re
import sys
from pathlib import Path
from typing import List

# Resolve API
sys.path.append(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules")
try:
    import DaVinciResolveScript as dvr
except Exception:
    dvr = None

# Qt
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QDialog,  # Added
    QSpinBox,
)


DEFAULT_ROOT = r"D:\Projects"
SEQ_EXTENSIONS: set[str] = {".exr", ".png", ".jpg", ".jpeg"}


def get_resolve():
    try:
        resolve = dvr.scriptapp("Resolve")
        if resolve:
            return resolve
    except Exception:
        pass

    try:
        resolve = fu.GetResolve()  # noqa: F821
        if resolve:
            return resolve
    except Exception:
        pass

    raise RuntimeError("Cannot connect to DaVinci Resolve.")


try:
    resolve = get_resolve()
except Exception:
    resolve = None
project = None
media_pool = None

try:
    project = resolve.GetProjectManager().GetCurrentProject()
    if project:
        media_pool = project.GetMediaPool()
except Exception:
    project = None
    media_pool = None


class ProgressDialog(QDialog):
    def __init__(self, maximum, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importing Sequences...")
        self.setModal(True)
        self.setFixedSize(400, 80)
        layout = QVBoxLayout(self)
        self.progress = QProgressBar(self)
        self.progress.setMinimum(0)
        self.progress.setMaximum(maximum)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)
        self.setLayout(layout)

    def setValue(self, value) -> None:
        self.progress.setValue(value)
        QApplication.processEvents()


class ShotLoaderPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Shot Loader")
        self.resize(980, 620)
        self.root_path: str = DEFAULT_ROOT if os.path.isdir(DEFAULT_ROOT) else ""
        self.row_data = {}
        self.row_counter = 0
        self.playback_files: list[str] = []
        self.playback_index = 0
        self.playback_fps = 24
        self.current_frame_path = ""
        self.current_sequence = None
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_frame)
        self._build_ui()
        if self.root_path:
            self.populate_tree()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        toolbar = QHBoxLayout()

        self.browse_btn = QPushButton("Select Folder")
        self.browse_btn.clicked.connect(self.select_folder)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.populate_tree)
        self.import_btn = QPushButton("Import Checked Sequences && Create Timeline")
        self.import_btn.clicked.connect(self.import_all_and_create_timeline)
        self.path_label = QLabel(self.root_path or "No folder selected")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        toolbar.addWidget(self.browse_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.path_label, 1)

        content = QHBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Sequence", "Frames", "Range", "Ext"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self.on_tree_selection)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.tree.setColumnWidth(0, 420)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 120)
        self.tree.setColumnWidth(3, 60)

        right_col = QVBoxLayout()
        self.preview = QLabel("Select a sequence")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 220)
        self.preview.setStyleSheet("border:1px solid #666; background:#1e1e1e;")
        self.meta = QTextEdit()
        self.meta.setReadOnly(True)
        self.meta.setPlaceholderText("Metadata will appear here")

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.play_selected_sequence)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_playback)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.fps_label = QLabel("FPS")
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(self.playback_fps)
        self.fps_spin.valueChanged.connect(self.set_playback_fps)

        controls.addWidget(self.play_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.fps_label)
        controls.addWidget(self.fps_spin)

        self.status = QLabel("Ready")
        self.progress = None

        right_col.addWidget(self.preview)
        right_col.addLayout(controls)
        right_col.addWidget(self.meta, 1)
        right_col.addWidget(self.status)

        content.addWidget(self.tree, 3)
        content.addLayout(right_col, 2)

        root_layout.addLayout(toolbar)
        root_layout.addLayout(content, 1)
        self.setLayout(root_layout)

    def on_tree_item_clicked(self, item, column):
        row_id = item.data(0, Qt.UserRole)
        seq = self.row_data.get(row_id)
        if seq:
            self.current_sequence = seq
            self.play_sequence(seq)

    def get_selected_sequence(self):
        selected = self.tree.selectedItems()
        if not selected:
            return self.current_sequence

        row_id = selected[0].data(0, Qt.UserRole)
        seq = self.row_data.get(row_id)
        if seq:
            self.current_sequence = seq
        return seq

    def play_selected_sequence(self):
        seq = self.get_selected_sequence()
        if not seq:
            self.status.setText("No sequence selected")
            return

        if self.playback_files and self.current_sequence == seq and not self.play_timer.isActive():
            interval_ms = max(1, int(1000 / self.playback_fps))
            self.play_timer.start(interval_ms)
            self.status.setText("Resumed sequence: {}".format(seq["seq_key"]))
            return

        self.play_sequence(seq)

    def pause_playback(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.status.setText("Paused")

    def stop_playback(self):
        self.play_timer.stop()
        self.playback_index = 0
        if self.playback_files:
            self.show_frame(self.playback_files[0])
        self.status.setText("Stopped")

    def set_playback_fps(self, fps):
        self.playback_fps = int(fps)
        if self.play_timer.isActive():
            interval_ms = max(1, int(1000 / self.playback_fps))
            self.play_timer.start(interval_ms)

    @staticmethod
    def _sequence_file_pattern(first_file):
        base_name = os.path.basename(first_file)
        match = re.match(r"(.+?)([._-]?)(\d{3,})(\.[^.]+)$", base_name)
        if not match:
            return None
        prefix, separator, digits, extension = match.groups()
        return prefix, separator, len(digits), extension

    def build_sequence_file_list(self, seq) -> list[str]:
        pattern = self._sequence_file_pattern(seq["first_file"])
        if not pattern:
            return []

        prefix, separator, padding, extension = pattern
        folder = seq["folder"]
        files: list[str] = []
        for frame in range(int(seq["start_index"]), int(seq["end_index"]) + 1):
            frame_name = "{}{}{:0{}d}{}".format(prefix, separator, frame, padding, extension)
            frame_path = os.path.join(folder, frame_name)
            if os.path.exists(frame_path):
                files.append(frame_path)
        return files

    def show_frame(self, frame_path):
        pixmap = QPixmap(frame_path)
        if pixmap.isNull():
            self.preview.setText("Cannot load frame")
            return

        scaled = pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)
        self.current_frame_path = frame_path

    def play_sequence(self, seq):
        self.play_timer.stop()
        self.current_sequence = seq
        self.playback_files = self.build_sequence_file_list(seq)
        self.playback_index = 0

        if not self.playback_files:
            self.preview.setText("No readable frames")
            self.status.setText("Playback failed: no readable frames")
            return

        self.show_frame(self.playback_files[0])
        interval_ms = max(1, int(1000 / self.playback_fps))
        self.play_timer.start(interval_ms)
        self.status.setText("Playing sequence: {}".format(seq["seq_key"]))

    def _advance_frame(self):
        if not self.playback_files:
            self.play_timer.stop()
            return

        self.playback_index = (self.playback_index + 1) % len(self.playback_files)
        self.show_frame(self.playback_files[self.playback_index])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_frame_path:
            self.show_frame(self.current_frame_path)

    def next_row_id(self) -> str:
        self.row_counter += 1
        return "row_{}".format(self.row_counter)

    @staticmethod
    def ensure_media_pool():
        global resolve, project, media_pool
        if media_pool:
            return media_pool

        try:
            resolve = get_resolve()
            project = resolve.GetProjectManager().GetCurrentProject()
            media_pool = project.GetMediaPool() if project else None
        except Exception:
            media_pool = None

        return media_pool

    @staticmethod
    def norm_path(path) -> str:
        return str(path).replace("\\", "/")

    @staticmethod
    def thumb_path(first_file) -> str:
        return os.path.join(os.path.dirname(first_file), ".thumb_{}.jpg".format(os.path.basename(first_file)))

    def detect_sequences(self, folder):
        for dirpath, _dirs, files in os.walk(folder):
            seq_map = {}
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in SEQ_EXTENSIONS:
                    continue

                match: re.Match[str] | None = re.match(r"(.+?)([._-]?)(\d{3,})(\.[^.]+)$", name)
                if not match:
                    continue

                seq_key: str | os.Any = match.group(1) + match.group(2) + match.group(4)
                seq_map.setdefault(seq_key, []).append(name)

            for seq_key, seq_files in seq_map.items():
                if len(seq_files) < 2:
                    continue

                seq_files = sorted(seq_files)
                first_name = seq_files[0]
                last_name = seq_files[-1]

                first_match: re.Match[str] | None = re.search(r"(\d{3,})(\.[^.]+)$", first_name)
                last_match: re.Match[str] | None = re.search(r"(\d{3,})(\.[^.]+)$", last_name)
                start_index: int = int(first_match.group(1)) if first_match else 0
                end_index: int = int(last_match.group(1)) if last_match else len(seq_files) - 1

                name_match: re.Match[str] | None = re.match(r"(.+?)([._-]?)(\d{3,})(\.[^.]+)$", first_name)
                if not name_match:
                    continue

                padding: int = len(name_match.group(3))
                pattern_printf: str = os.path.join(
                    dirpath,
                    "{}{}%0{}d{}".format(name_match.group(1), name_match.group(2), padding, name_match.group(4)),
                )
                pattern_hash: str = os.path.join(
                    dirpath,
                    "{}{}{}{}".format(name_match.group(1), name_match.group(2), "#" * padding, name_match.group(4)),
                )

                yield {
                    "seq_key": seq_key,
                    "folder": dirpath,
                    "folder_name": Path(dirpath).name or dirpath,
                    "first_file": os.path.join(dirpath, first_name),
                    "frames": len(seq_files),
                    "start_index": start_index,
                    "end_index": end_index,
                    "extension": os.path.splitext(first_name)[1].lower(),
                    "pattern_printf": pattern_printf,
                    "pattern_hash": pattern_hash,
                }

    def populate_tree(self) -> None:
        self.tree.clear()
        self.row_data = {}
        if not self.root_path or not os.path.isdir(self.root_path):
            self.status.setText("Invalid folder")
            return

        count = 0
        for seq in self.detect_sequences(self.root_path):
            row_id: str = self.next_row_id()
            self.row_data[row_id] = seq

            item = QTreeWidgetItem([
                "{} / {}".format(seq["folder_name"], seq["seq_key"]),
                str(seq["frames"]),
                "{}-{}".format(seq["start_index"], seq["end_index"]),
                seq["extension"],
            ])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)
            item.setData(0, Qt.UserRole, row_id)
            self.tree.addTopLevelItem(item)
            count += 1

        self.status.setText("Found {} sequence(s)".format(count))

    def get_checked_row_ids(self) -> list[str]:
        checked_row_ids: list[str] = []
        total_items = self.tree.topLevelItemCount()
        for index in range(total_items):
            item = self.tree.topLevelItem(index)
            if not item:
                continue
            if item.checkState(0) == Qt.Checked:
                row_id = item.data(0, Qt.UserRole)
                if row_id:
                    checked_row_ids.append(row_id)
        return checked_row_ids

    def select_folder(self) -> None:
        start_dir: str = self.root_path if self.root_path else DEFAULT_ROOT
        folder: str = QFileDialog.getExistingDirectory(self, "Select Sequence Folder", start_dir)
        if folder:
            self.root_path: str = folder
            self.path_label.setText(folder)
            self.populate_tree()

    @staticmethod
    def clip_uid(clip) -> str:
        try:
            uid = clip.GetUniqueId()
            if uid is not None:
                return str(uid)
        except Exception:
            pass
        return str(id(clip))

    def snapshot_pool(self):
        current_media_pool = self.ensure_media_pool()
        if not current_media_pool:
            return set(), []
        clips = list(current_media_pool.GetRootFolder().GetClipList() or [])
        ids: set[str] = {self.clip_uid(c) for c in clips}
        return ids, clips

    def import_sequence_item(self, seq):
        current_media_pool = self.ensure_media_pool()
        if not current_media_pool:
            return []

        first_file: str = self.norm_path(seq["first_file"])
        pattern_printf: str = self.norm_path(seq["pattern_printf"])
        pattern_hash: str = self.norm_path(seq["pattern_hash"])

        print("[Shot Loader] Importing: {}".format(seq["seq_key"]))

        attempts = [
            [{"FilePath": pattern_printf, "StartIndex": int(seq["start_index"]), "EndIndex": int(seq["end_index"])}],
            [{"FilePath": pattern_hash, "StartIndex": int(seq["start_index"]), "EndIndex": int(seq["end_index"])}],
            [first_file],
            first_file,
        ]

        for payload in attempts:
            try:
                result = current_media_pool.ImportMedia(payload)
            except Exception as exc:
                print("[Shot Loader] ImportMedia error: {}".format(exc))
                continue

            if result:
                print("[Shot Loader] Import OK with payload: {}".format(payload))
                if isinstance(result, (list, tuple)):
                    return [c for c in result if c]
                return [result]

        print("[Shot Loader] Import FAILED for {}".format(seq["seq_key"]))
        return []

    def import_all_and_create_timeline(self) -> None:
        current_media_pool = self.ensure_media_pool()
        if not current_media_pool:
            self.status.setText("Resolve project/media pool unavailable")
            return

        checked_row_ids = self.get_checked_row_ids()
        total: int = len(checked_row_ids)
        if total == 0:
            self.status.setText("No checked sequence(s) to import")
            return
        self.status.setText("Importing checked sequences...")
        progress_dialog: ProgressDialog = ProgressDialog(total, self)
        progress_dialog.show()
        before_ids, _before_clips = self.snapshot_pool()
        imported_clips = []
        imported_clip_ids = set()
        for i, row_id in enumerate(checked_row_ids):
            seq = self.row_data.get(row_id)
            if not seq:
                continue
            clips = self.import_sequence_item(seq)
            for clip in clips:
                uid = self.clip_uid(clip)
                if uid not in imported_clip_ids:
                    imported_clip_ids.add(uid)
                    imported_clips.append(clip)
            progress_dialog.setValue(i + 1)
        if not imported_clips:
            after_ids, after_clips = self.snapshot_pool()
            new_ids: set[str] = after_ids - before_ids
            for clip in after_clips:
                uid: str = self.clip_uid(clip)
                if uid in new_ids:
                    imported_clips.append(clip)
        if not imported_clips:
            self.status.setText("Import failed")
            progress_dialog.close()
            return
        timeline_base: str = "{}_Timeline".format(Path(self.root_path).name or "Shots")
        timeline_name: str = timeline_base
        timeline = None
        for idx in range(0, 100):
            try_name = timeline_name if idx == 0 else "{}_{}".format(timeline_base, idx + 1)
            try:
                timeline = current_media_pool.CreateEmptyTimeline(try_name)
            except Exception:
                timeline = None
            if timeline:
                timeline_name = try_name
                break
        if not timeline:
            self.status.setText("Imported {} clips, timeline creation failed".format(len(imported_clips)))
            progress_dialog.close()
            return
        try:
            appended = current_media_pool.AppendToTimeline(imported_clips)
        except Exception as exc:
            print("[Shot Loader] AppendToTimeline error: {}".format(exc))
            appended = False
        if appended:
            self.status.setText(
                "Timeline '{}' created with {} clips from {} checked sequence(s)".format(
                    timeline_name,
                    len(imported_clips),
                    total,
                )
            )
        else:
            self.status.setText("Timeline created, append failed")
        progress_dialog.setValue(total)
        progress_dialog.close()

    def on_tree_selection(self) -> None:
        selected: List[QTreeWidgetItem] = self.tree.selectedItems()
        if not selected:
            self.play_timer.stop()
            self.playback_files = []
            self.current_frame_path = ""
            self.preview.setText("Select a sequence")
            self.meta.setPlainText("")
            return

        item: QTreeWidgetItem = selected[0]
        row_id = item.data(0, Qt.UserRole)
        seq = self.row_data.get(row_id)
        if not seq:
            return

        first_file = seq["first_file"]
        if not self.play_timer.isActive():
            self.show_frame(first_file)

        meta_lines: list[str] = [
            "Sequence : {}".format(seq["seq_key"]),
            "Folder   : {}".format(seq["folder"]),
            "First    : {}".format(seq["first_file"]),
            "Pattern% : {}".format(seq["pattern_printf"]),
            "Pattern# : {}".format(seq["pattern_hash"]),
            "Frames   : {}".format(seq["frames"]),
            "Range    : {}-{}".format(seq["start_index"], seq["end_index"]),
        ]
        self.meta.setPlainText("\n".join(meta_lines))


app: QCoreApplication | QApplication = QApplication.instance() or QApplication(sys.argv)
panel = ShotLoaderPanel()
panel.show()
app.exec()
