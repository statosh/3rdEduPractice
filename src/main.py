import sys
import os
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QSplitter,
    QFileDialog, QProgressDialog, QMenu, QFrame, QHeaderView,
    QStyle, QSizePolicy, QSystemTrayIcon, QMessageBox
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QObject, QThread, QSize, QFile, QIODevice
)
from PySide6.QtGui import QAction, QIcon, QFont, QClipboard, QPalette, QColor
from PySide6.QtUiTools import QUiLoader

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from scanner import DiskScanner
from chart import build_pie_chart
from export import export_to_csv

import signal

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    return f"{size_bytes} Б"


class UiLoader(QUiLoader):
    def __init__(self, base_instance=None):
        super().__init__(base_instance)
        self.base_instance = base_instance

    def createWidget(self, className, parent=None, name=''):
        if parent is None and self.base_instance:
            return self.base_instance
        return super().createWidget(className, parent, name)


class ScannerWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(dict, dict, dict)
    error = Signal(str)

    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
        self._is_running = False

    def scan(self, path):
        self._is_running = True
        self.scanner.reset()
        self.scanner.progress_callback = self._on_progress
        self.scanner.done_callback = self._on_done
        thread = threading.Thread(target=self._scan_thread, args=(path,), daemon=True)
        thread.start()

    def _scan_thread(self, path):
        try:
            self.scanner.scan(path)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current, total):
        if self._is_running:
            self.progress.emit(current, total)

    def _on_done(self, folder_sizes, file_sizes, file_types):
        if self._is_running:
            self.finished.emit(folder_sizes, file_sizes, file_types)

    def stop(self):
        self._is_running = False
        self.scanner.stop()


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, path, item_type, parent=None):
        super().__init__(parent)
        self.full_path = path
        self.item_type = item_type
        self._loaded = False

    def is_loaded(self):
        return self._loaded

    def set_loaded(self, loaded=True):
        self._loaded = loaded


class DiskAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self._load_ui()

        self.scanner = DiskScanner()
        self.worker = ScannerWorker(self.scanner)
        self.folder_sizes = {}
        self.file_sizes = {}
        self.file_types = {}
        self.selected_path = None
        self.full_selected_path = ""
        self.tree_cache = {}
        self.progress_dialog = None

        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_scan_complete)
        self.worker.error.connect(self._on_scan_error)

        self._setup_ui()
        self._create_tray_icon()
        self._connect_signals()

        self._path_update_timer = QTimer()
        self._path_update_timer.setSingleShot(True)
        self._path_update_timer.timeout.connect(self._refresh_path_display)

        self.current_theme = "base"
        self._load_theme("base")

    def _load_ui(self):
        ui_file_path = os.path.join(base_dir, "ui", "main_window.ui")

        if not os.path.exists(ui_file_path):
            QMessageBox.critical(
                self, "Ошибка",
                f"Файл интерфейса не найден: {ui_file_path}\n"
                "Создайте интерфейс в Qt Designer и сохраните как ui/main_window.ui"
            )
            sys.exit(1)

        try:
            ui_file = QFile(ui_file_path)
            ui_file.open(QFile.ReadOnly)

            loader = UiLoader(self)
            self.ui = loader.load(ui_file)
            ui_file.close()

            self.pathLabel = self.findChild(QLabel, "pathLabel")
            self.browseButton = self.findChild(QPushButton, "browseButton")
            self.scanButton = self.findChild(QPushButton, "scanButton")
            self.exportButton = self.findChild(QPushButton, "exportButton")
            self.themeButton = self.findChild(QPushButton, "themeButton")
            self.statusLabel = self.findChild(QLabel, "statusLabel")
            self.treeWidget = self.findChild(QTreeWidget, "treeWidget")
            self.pathInfoValue = self.findChild(QLabel, "pathInfoValue")
            self.copyPathButton = self.findChild(QPushButton, "copyPathButton")
            self.chartContainer = self.findChild(QWidget, "chartContainer")
            self.typesTextLabel = self.findChild(QLabel, "typesTextLabel")
            self.splitter = self.findChild(QSplitter, "splitter")

            if self.chartContainer:
                self.chartLayout = self.chartContainer.layout()
                if not self.chartLayout:
                    self.chartLayout = QVBoxLayout(self.chartContainer)
                    self.chartLayout.setContentsMargins(0, 0, 0, 0)
                    self.chartLayout.setSpacing(0)

        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка загрузки UI",
                f"Не удалось загрузить интерфейс: {str(e)}"
            )
            sys.exit(1)

    def _setup_ui(self):
        if self.treeWidget:
            self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.treeWidget.setRootIsDecorated(True)
            self.treeWidget.setAnimated(True)
            self.treeWidget.setExpandsOnDoubleClick(True)

        self._apply_panel_styles()

    def _apply_panel_styles(self):
        left_panel = self.findChild(QWidget, "leftPanel")
        right_panel = self.findChild(QWidget, "rightPanel")
        top_frame = self.findChild(QFrame, "topFrame")
        types_frame = self.findChild(QFrame, "typesFrame")

        if left_panel:
            left_panel.setObjectName("leftPanel")
        if right_panel:
            right_panel.setObjectName("rightPanel")

    def _connect_signals(self):
        if self.browseButton:
            self.browseButton.clicked.connect(self._browse_folder)

        if self.scanButton:
            self.scanButton.clicked.connect(self._start_scan)

        if self.exportButton:
            self.exportButton.clicked.connect(self._export_csv)

        if self.themeButton:
            self.themeButton.clicked.connect(self._toggle_theme)

        if self.treeWidget:
            self.treeWidget.customContextMenuRequested.connect(self._show_context_menu)
            self.treeWidget.itemExpanded.connect(self._on_tree_expanded)
            self.treeWidget.currentItemChanged.connect(self._on_tree_selection_changed)

        if self.copyPathButton:
            self.copyPathButton.clicked.connect(self._copy_path_to_clipboard)

    def _load_theme(self, theme_name):
        theme_file = os.path.join(base_dir, "style", f"{theme_name}.qss")
        if os.path.exists(theme_file):
            with open(theme_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _toggle_theme(self):
        if self.current_theme == "base":
            self.current_theme = "dark"
        else:
            self.current_theme = "base"
        self._load_theme(self.current_theme)

    def _create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = os.path.join(base_dir, "../img/icon.ico")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("A-One Disk Analyser")

        tray_menu = QMenu()

        show_action = QAction("Открыть", self)
        show_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Закрыть", self)
        quit_action.triggered.connect(self._quit_from_tray)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_from_tray(self):
        self.worker.stop()

        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            self.tray_icon = None

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        QApplication.quit()

    def closeEvent(self, event):
        if hasattr(self, 'tray_icon') and self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
        else:
            self._cleanup()
            event.accept()

    def _cleanup(self):
        self.worker.stop()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        if self.progress_dialog:
            self.progress_dialog.close()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку или диск")
        if folder:
            self.pathLabel.setText(f"Папка: {folder}")
            self.selected_path = folder
            self.scanButton.setEnabled(True)

    def _start_scan(self):
        if not self.selected_path:
            return

        self.scanButton.setEnabled(False)
        self.browseButton.setEnabled(False)
        self.exportButton.setEnabled(False)
        self.statusLabel.setText("Сканирование...")
        self.statusLabel.setStyleSheet("color: #f39c12;")

        self.treeWidget.clear()
        self.typesTextLabel.setText("Сканирование...")
        self._clear_chart()
        self.tree_cache.clear()
        self.pathInfoValue.setText("")
        self.full_selected_path = ""

        self.progress_dialog = QProgressDialog(
            "Выполняется сканирование...", "Отмена", 0, 0, self
        )
        self.progress_dialog.setWindowTitle("Сканирование...")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._cancel_scan)
        self.progress_dialog.show()

        self.worker.scan(self.selected_path)

    def _cancel_scan(self):
        self.worker.stop()
        self.statusLabel.setText("Отменено")
        self.statusLabel.setStyleSheet("color: #e74c3c;")
        self.scanButton.setEnabled(True)
        self.browseButton.setEnabled(True)
        self.exportButton.setEnabled(True)

    def _update_progress(self, current, total):
        if self.progress_dialog and total > 0:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(
                f"Выполняется сканирование... ({current}/{total})"
            )

    def _on_scan_complete(self, folder_sizes, file_sizes, file_types):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        self.scanButton.setEnabled(True)
        self.browseButton.setEnabled(True)
        self.exportButton.setEnabled(True)

        if not folder_sizes and not file_sizes:
            self.statusLabel.setText("Нет данных")
            self.statusLabel.setStyleSheet("color: #e74c3c;")
            self.typesTextLabel.setText("Сканирование не дало результатов")
            return

        self.folder_sizes = folder_sizes
        self.file_sizes = file_sizes
        self.file_types = file_types

        self.statusLabel.setText("Готово")
        self.statusLabel.setStyleSheet("color: #2ecc71;")

        root_norm = os.path.normpath(self.selected_path)
        total_size = self.folder_sizes.get(self.selected_path, 0)
        if total_size == 0:
            total_size = self.folder_sizes.get(root_norm, 0)
        if total_size == 0:
            total_size = sum(self.file_types.values())

        self._build_tree_cache()
        self._populate_tree(root_norm, total_size)
        self._update_types_info()
        self._build_chart(root_norm, total_size)

    def _on_scan_error(self, error_msg):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        self.statusLabel.setText(f"Ошибка: {error_msg}")
        self.statusLabel.setStyleSheet("color: #e74c3c;")
        self.scanButton.setEnabled(True)
        self.browseButton.setEnabled(True)
        self.exportButton.setEnabled(True)

    def _build_tree_cache(self):
        self.tree_cache.clear()
        root_norm = os.path.normpath(self.selected_path)

        for path in self.folder_sizes:
            path_norm = os.path.normpath(path)
            if path_norm == root_norm:
                continue

            parent = os.path.normpath(os.path.dirname(path_norm))
            if parent not in self.tree_cache:
                self.tree_cache[parent] = {"folders": [], "files": []}

            entry = (path, self.folder_sizes[path], "folder")
            if entry not in self.tree_cache[parent]["folders"]:
                self.tree_cache[parent]["folders"].append(entry)

        for filepath, size in self.file_sizes.items():
            file_norm = os.path.normpath(filepath)
            parent = os.path.normpath(os.path.dirname(file_norm))

            if parent not in self.tree_cache:
                self.tree_cache[parent] = {"folders": [], "files": []}

            entry = (filepath, size, "file")
            self.tree_cache[parent]["files"].append(entry)

        for parent in self.tree_cache:
            self.tree_cache[parent]["folders"].sort(key=lambda x: x[1], reverse=True)
            self.tree_cache[parent]["files"].sort(key=lambda x: x[1], reverse=True)

    def _populate_tree(self, root_norm, total_size):
        if root_norm in self.tree_cache:
            self._populate_children(None, root_norm, total_size)
        else:
            item = QTreeWidgetItem(self.treeWidget)
            item.setText(0, "Нет данных")
            item.setText(1, "0 Б")
            item.setText(2, "0%")

    def _populate_children(self, parent_item, parent_path_norm, parent_size):
        if parent_path_norm not in self.tree_cache:
            return

        cache = self.tree_cache[parent_path_norm]
        folders = cache["folders"]
        files = cache["files"]

        all_entries = []

        for entry in folders:
            path, size, etype = entry
            all_entries.append((size, "folder", entry))

        if files:
            files_total_size = sum(size for _, size, _ in files)
            all_entries.append((files_total_size, "virtual_folder", files))

        all_entries.sort(key=lambda x: x[0], reverse=True)

        for size, entry_type, data in all_entries:
            if parent_size > 0:
                percent = (size / parent_size) * 100
                percent_str = f"{percent:.1f}%"
            else:
                percent_str = "0%"

            if entry_type == "folder":
                path, _, _ = data
                name = os.path.basename(path) if os.path.basename(path) else path
                path_norm = os.path.normpath(path)

                if parent_item:
                    item = TreeWidgetItem(path_norm, "folder", parent_item)
                else:
                    item = TreeWidgetItem(path_norm, "folder")
                    self.treeWidget.addTopLevelItem(item)

                item.setText(0, f"📁 {name}")
                item.setText(1, format_size(size))
                item.setText(2, percent_str)
                item.setToolTip(0, path)

                if path_norm in self.tree_cache:
                    dummy = QTreeWidgetItem(item)
                    dummy.setText(0, "Загрузка...")

            elif entry_type == "virtual_folder":
                files_list = data
                virtual_path = parent_path_norm + os.sep + "<файлы>"

                if parent_item:
                    item = TreeWidgetItem(virtual_path, "virtual_folder", parent_item)
                else:
                    item = TreeWidgetItem(virtual_path, "virtual_folder")
                    self.treeWidget.addTopLevelItem(item)

                item.setText(0, f"📁 <файлы> ({len(files_list)} шт.)")
                item.setText(1, format_size(size))
                item.setText(2, percent_str)

                dummy = QTreeWidgetItem(item)
                dummy.setText(0, "Загрузка...")

    def _on_tree_expanded(self, item):
        if not isinstance(item, TreeWidgetItem) or item.is_loaded():
            return

        while item.childCount() > 0:
            item.removeChild(item.child(0))

        if item.item_type == "folder":
            path_norm = item.full_path
            parent_size = self.folder_sizes.get(path_norm, 0)
            if parent_size == 0:
                for orig_path, size in self.folder_sizes.items():
                    if os.path.normpath(orig_path) == path_norm:
                        parent_size = size
                        break
            self._populate_children(item, path_norm, parent_size)

        elif item.item_type == "virtual_folder":
            real_parent = item.full_path.rsplit(os.sep + "<файлы>", 1)[0]
            if real_parent in self.tree_cache:
                files = self.tree_cache[real_parent]["files"]
                files_total_size = sum(size for _, size, _ in files)

                for path, size, etype in files:
                    name = os.path.basename(path) if os.path.basename(path) else path
                    percent = (size / files_total_size * 100) if files_total_size > 0 else 0

                    file_item = TreeWidgetItem(path, "file", item)
                    file_item.setText(0, f"📄 {name}")
                    file_item.setText(1, format_size(size))
                    file_item.setText(2, f"{percent:.1f}%")
                    file_item.setToolTip(0, path)

        item.set_loaded(True)

    def _on_tree_selection_changed(self, current, previous):
        if not current or not isinstance(current, TreeWidgetItem):
            self.full_selected_path = ""
            self.pathInfoValue.setText("")
            return

        if current.item_type == "virtual_folder":
            self.full_selected_path = current.full_path.rsplit(os.sep + "<файлы>", 1)[0]
        elif current.item_type in ("folder", "file"):
            self.full_selected_path = current.full_path
        else:
            self.full_selected_path = ""

        self._refresh_path_display()

    def _show_context_menu(self, pos):
        item = self.treeWidget.itemAt(pos)
        if not item or not isinstance(item, TreeWidgetItem):
            return

        if item.item_type not in ("folder", "file", "virtual_folder"):
            return

        menu = QMenu(self)
        open_action = menu.addAction("📂 Открыть расположение")
        open_action.triggered.connect(self._open_file_location)
        menu.exec(self.treeWidget.viewport().mapToGlobal(pos))

    def _open_file_location(self):
        item = self.treeWidget.currentItem()
        if not item or not isinstance(item, TreeWidgetItem):
            return

        path = item.full_path
        if item.item_type == "virtual_folder":
            path = path.rsplit(os.sep + "<файлы>", 1)[0]

        if not path or not os.path.exists(path):
            return

        if item.item_type == "file":
            folder = os.path.dirname(path)
            if os.path.exists(folder):
                os.startfile(folder)
        else:
            os.startfile(path)

    def _build_chart(self, root_norm, total_size):
        self._clear_chart()

        if root_norm in self.tree_cache:
            folders = self.tree_cache[root_norm]["folders"]
            top8 = folders[:8]

            chart_data = {}
            for path, size, etype in top8:
                name = os.path.basename(path) if os.path.basename(path) else path
                chart_data[f"📁 {name}"] = size

            other_size = total_size - sum(size for _, size, _ in top8)
            if other_size > 0:
                chart_data["Прочее"] = max(0, other_size)
        else:
            chart_data = {"Все данные": total_size}

        if chart_data and self.chartLayout:
            canvas = build_pie_chart(self.chartContainer, chart_data, scan_path=self.selected_path)
            self.chartLayout.addWidget(canvas)

    def _clear_chart(self):
        if self.chartLayout:
            while self.chartLayout.count():
                child = self.chartLayout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

    def _update_types_info(self):
        types_lines = []
        for ftype, size in self.file_types.items():
            types_lines.append(f"{ftype}: {format_size(size)}")
        self.typesTextLabel.setText("  |  ".join(types_lines))

    def _refresh_path_display(self):
        path = self.full_selected_path
        if path:
            shortened = self._shorten_path(path)
            self.pathInfoValue.setText(shortened)
        else:
            self.pathInfoValue.setText("")

    def _shorten_path(self, path: str) -> str:
        if not path:
            return path

        path = os.path.normpath(path)
        metrics = self.pathInfoValue.fontMetrics()
        max_width = self.pathInfoValue.width() - 20

        if metrics.horizontalAdvance(path) <= max_width:
            return path

        parts = path.split(os.sep)
        if len(parts) <= 2:
            return path

        best = f"{parts[0]}{os.sep}...{os.sep}{parts[-1]}"
        left, right = 1, 1

        while left + right < len(parts):
            test = f"{os.sep.join(parts[:left+1])}{os.sep}...{os.sep}{os.sep.join(parts[-right:])}"
            if metrics.horizontalAdvance(test) <= max_width:
                best = test
                left += 1
            else:
                break

        return best

    def _copy_path_to_clipboard(self):
        path = self.full_selected_path
        if path:
            QApplication.clipboard().setText(path)
            self.copyPathButton.setText("✓")
            QTimer.singleShot(1000, lambda: self.copyPathButton.setText("📋"))

    def _export_csv(self):
        if not self.folder_sizes:
            return

        filepath = export_to_csv(
            self.folder_sizes, self.file_sizes, self.file_types, self.selected_path
        )
        self.statusLabel.setText(f"Сохранено: {os.path.basename(filepath)}")
        self.statusLabel.setStyleSheet("color: #2ecc71;")


def signal_handler(signum, frame):
    QApplication.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("A-One Disk Analyser")
    app.setQuitOnLastWindowClosed(False)

    icon_path = os.path.join(base_dir, "../img/icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = DiskAnalyzerApp()
    window.show()

    exit_code = app.exec()
    window._cleanup()
    sys.exit(exit_code)