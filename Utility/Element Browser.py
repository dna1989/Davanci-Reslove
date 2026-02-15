import os
import re
import sys
from pathlib import Path

# Resolve API
sys.path.append(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules")
import DaVinciResolveScript as dvr

# Qt
from PySide6.QtCore import Qt
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
)


DEFAULT_ROOT = r"D:\Projects"
SEQ_EXTENSIONS = {".exr", ".png", ".jpg", ".jpeg"}


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


resolve = get_resolve()
project = resolve.GetProjectManager().GetCurrentProject()
media_pool = project.GetMediaPool()


class ShotLoaderPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shot Loader")
        self.resize(980, 620)

        self.root_path = DEFAULT_ROOT if os.path.isdir(DEFAULT_ROOT) else ""
        self.row_data = {}
        self.row_counter = 0

        self._build_ui()
        if self.root_path:
            self.populate_tree()

    def _build_ui(self):
        root_layout = QVBoxLayout()
        toolbar = QHBoxLayout()

        self.browse_btn = QPushButton("Select Folder")
        self.browse_btn.clicked.connect(self.select_folder)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.populate_tree)

        self.import_btn = QPushButton("Import All Sequences && Create Timeline")
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

        self.status = QLabel("Ready")

        right_col.addWidget(self.preview)
        right_col.addWidget(self.meta, 1)
        right_col.addWidget(self.status)

        content.addWidget(self.tree, 3)
        content.addLayout(right_col, 2)

        root_layout.addLayout(toolbar)
        root_layout.addLayout(content, 1)
        self.setLayout(root_layout)

    def next_row_id(self):
        self.row_counter += 1
        return "row_{}".format(self.row_counter)

    @staticmethod
    def norm_path(path):
        return str(path).replace("\\", "/")

    @staticmethod
    def thumb_path(first_file):
        return os.path.join(os.path.dirname(first_file), ".thumb_{}.jpg".format(os.path.basename(first_file)))

    def detect_sequences(self, folder):
        for dirpath, _dirs, files in os.walk(folder):
            seq_map = {}
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in SEQ_EXTENSIONS:
                    continue

                match = re.match(r"(.+?)([._-]?)(\d{3,})(\.[^.]+)$", name)
                if not match:
                    continue

                seq_key = match.group(1) + match.group(2) + match.group(4)
                seq_map.setdefault(seq_key, []).append(name)

            for seq_key, seq_files in seq_map.items():
                if len(seq_files) < 2:
                    continue

                seq_files = sorted(seq_files)
                first_name = seq_files[0]
                last_name = seq_files[-1]

                first_match = re.search(r"(\d{3,})(\.[^.]+)$", first_name)
                last_match = re.search(r"(\d{3,})(\.[^.]+)$", last_name)
                start_index = int(first_match.group(1)) if first_match else 0
                end_index = int(last_match.group(1)) if last_match else len(seq_files) - 1

                name_match = re.match(r"(.+?)([._-]?)(\d{3,})(\.[^.]+)$", first_name)
                if not name_match:
                    continue

                padding = len(name_match.group(3))
                pattern_printf = os.path.join(
                    dirpath,
                    "{}{}%0{}d{}".format(name_match.group(1), name_match.group(2), padding, name_match.group(4)),
                )
                pattern_hash = os.path.join(
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

    def populate_tree(self):
        self.tree.clear()
        self.row_data = {}
        if not self.root_path or not os.path.isdir(self.root_path):
            self.status.setText("Invalid folder")
            return

        count = 0
        for seq in self.detect_sequences(self.root_path):
            row_id = self.next_row_id()
            self.row_data[row_id] = seq

            item = QTreeWidgetItem([
                "{} / {}".format(seq["folder_name"], seq["seq_key"]),
                str(seq["frames"]),
                "{}-{}".format(seq["start_index"], seq["end_index"]),
                seq["extension"],
            ])
            item.setData(0, Qt.UserRole, row_id)
            self.tree.addTopLevelItem(item)
            count += 1

        self.status.setText("Found {} sequence(s)".format(count))

    def select_folder(self):
        start_dir = self.root_path if self.root_path else DEFAULT_ROOT
        folder = QFileDialog.getExistingDirectory(self, "Select Sequence Folder", start_dir)
        if folder:
            self.root_path = folder
            self.path_label.setText(folder)
            self.populate_tree()

    @staticmethod
    def clip_uid(clip):
        try:
            uid = clip.GetUniqueId()
            if uid is not None:
                return str(uid)
        except Exception:
            pass
        return str(id(clip))

    def snapshot_pool(self):
        clips = list(media_pool.GetRootFolder().GetClipList() or [])
        ids = {self.clip_uid(c) for c in clips}
        return ids, clips

    def import_sequence_item(self, seq):
        first_file = self.norm_path(seq["first_file"])
        pattern_printf = self.norm_path(seq["pattern_printf"])
        pattern_hash = self.norm_path(seq["pattern_hash"])

        print("[Shot Loader] Importing: {}".format(seq["seq_key"]))

        attempts = [
            [{"FilePath": pattern_printf, "StartIndex": int(seq["start_index"]), "EndIndex": int(seq["end_index"])}],
            [{"FilePath": pattern_hash, "StartIndex": int(seq["start_index"]), "EndIndex": int(seq["end_index"])}],
            [first_file],
            first_file,
        ]

        for payload in attempts:
            try:
                result = media_pool.ImportMedia(payload)
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

    def import_all_and_create_timeline(self):
        total = self.tree.topLevelItemCount()
        if total == 0:
            self.status.setText("Nothing to import")
            return

        self.status.setText("Importing...")

        before_ids, _before_clips = self.snapshot_pool()
        imported_clips = []
        imported_clip_ids = set()

        for i in range(total):
            item = self.tree.topLevelItem(i)
            row_id = item.data(0, Qt.UserRole)
            seq = self.row_data.get(row_id)
            if not seq:
                continue

            clips = self.import_sequence_item(seq)
            for clip in clips:
                uid = self.clip_uid(clip)
                if uid not in imported_clip_ids:
                    imported_clip_ids.add(uid)
                    imported_clips.append(clip)

        if not imported_clips:
            # Resolve sometimes imports but returns empty list; detect by pool diff.
            after_ids, after_clips = self.snapshot_pool()
            new_ids = after_ids - before_ids
            for clip in after_clips:
                uid = self.clip_uid(clip)
                if uid in new_ids:
                    imported_clips.append(clip)

        if not imported_clips:
            self.status.setText("Import failed")
            return

        timeline_base = "{}_Timeline".format(Path(self.root_path).name or "Shots")
        timeline_name = timeline_base
        timeline = None

        for idx in range(0, 100):
            try_name = timeline_name if idx == 0 else "{}_{}".format(timeline_base, idx + 1)
            try:
                timeline = media_pool.CreateEmptyTimeline(try_name)
            except Exception:
                timeline = None
            if timeline:
                timeline_name = try_name
                break

        if not timeline:
            self.status.setText("Imported {} clips, timeline creation failed".format(len(imported_clips)))
            return

        try:
            appended = media_pool.AppendToTimeline(imported_clips)
        except Exception as exc:
            print("[Shot Loader] AppendToTimeline error: {}".format(exc))
            appended = False

        if appended:
            self.status.setText("Timeline '{}' created with {} clips".format(timeline_name, len(imported_clips)))
        else:
            self.status.setText("Timeline created, append failed")

    def on_tree_selection(self):
        selected = self.tree.selectedItems()
        if not selected:
            self.preview.setText("Select a sequence")
            self.meta.setPlainText("")
            return

        item = selected[0]
        row_id = item.data(0, Qt.UserRole)
        seq = self.row_data.get(row_id)
        if not seq:
            return

        first_file = seq["first_file"]
        thumb = self.thumb_path(first_file)
        if not os.path.exists(thumb):
            self.preview.setText("No thumbnail")
        else:
            self.preview.setText('<img src="file:///{}" width="320">'.format(thumb.replace("\\", "/")))

        meta_lines = [
            "Sequence : {}".format(seq["seq_key"]),
            "Folder   : {}".format(seq["folder"]),
            "First    : {}".format(seq["first_file"]),
            "Pattern% : {}".format(seq["pattern_printf"]),
            "Pattern# : {}".format(seq["pattern_hash"]),
            "Frames   : {}".format(seq["frames"]),
            "Range    : {}-{}".format(seq["start_index"], seq["end_index"]),
        ]
        self.meta.setPlainText("\n".join(meta_lines))


app = QApplication.instance() or QApplication(sys.argv)
panel = ShotLoaderPanel()
panel.show()
app.exec()
