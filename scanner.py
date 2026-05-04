import os
import threading
from collections import defaultdict


class DiskScanner:
    """Рекурсивный сканер диска с многопоточностью"""

    def __init__(self):
        self._stop_flag = threading.Event()
        self.progress_callback = None
        self.done_callback = None
        self.folder_sizes = defaultdict(int)
        self.file_sizes = defaultdict(int)
        self.file_types = {"видео": 0, "фото": 0, "документы": 0, "прочее": 0}
        self.processed_count = 0
        self.total_count = 0

        self.type_map = {
            "видео": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"},
            "фото": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".raw", ".heic", ".ico", ".svg"},
            "документы": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".json", ".xml", ".html", ".md"}
        }

    def stop(self):
        self._stop_flag.set()

    def reset(self):
        self._stop_flag.clear()
        self.folder_sizes.clear()
        self.file_sizes.clear()
        self.file_types = {"видео": 0, "фото": 0, "документы": 0, "прочее": 0}
        self.processed_count = 0
        self.total_count = 0

    def _classify_file(self, filepath: str) -> str:
        try:
            ext = os.path.splitext(filepath)[1].lower()
        except Exception:
            return "прочее"

        for ftype, extensions in self.type_map.items():
            if ext in extensions:
                return ftype
        return "прочее"

    def _count_items(self, path: str) -> int:
        """Быстрый подсчёт количества элементов (без stat)"""
        count = 0
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if self._stop_flag.is_set():
                        return count
                    try:
                        count += 1
                        if entry.is_dir(follow_symlinks=False):
                            count += self._count_items(entry.path)
                    except (PermissionError, OSError, FileNotFoundError):
                        pass
        except (PermissionError, OSError, FileNotFoundError):
            pass
        return count

    def _scan_directory(self, path: str) -> int:
        total = 0

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if self._stop_flag.is_set():
                        return total

                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            total += size
                            self.file_sizes[entry.path] = size
                            ftype = self._classify_file(entry.path)
                            self.file_types[ftype] += size
                            self.processed_count += 1

                        elif entry.is_dir(follow_symlinks=False):
                            self.processed_count += 1
                            dir_size = self._scan_directory(entry.path)
                            total += dir_size
                            self.folder_sizes[entry.path] = dir_size

                        if self.progress_callback and self.processed_count % 100 == 0:
                            self.progress_callback(
                                self.processed_count, self.total_count)

                    except (PermissionError, OSError, FileNotFoundError):
                        self.processed_count += 1
                        continue

        except (PermissionError, OSError, FileNotFoundError):
            pass

        return total

    def scan(self, root_path: str) -> threading.Thread:
        self.reset()

        def _scan_worker():
            try:
                self.total_count = self._count_items(root_path)

                self.processed_count = 0
                total_size = self._scan_directory(root_path)
                self.folder_sizes[root_path] = total_size

                if self.progress_callback:
                    self.progress_callback(self.total_count, self.total_count)

                if self.done_callback and not self._stop_flag.is_set():
                    self.done_callback(
                        dict(self.folder_sizes),
                        dict(self.file_sizes),
                        dict(self.file_types)
                    )

            except Exception as e:
                print(f"[Ошибка сканирования] {e}")
                import traceback
                traceback.print_exc()
                if self.done_callback:
                    self.done_callback(
                        dict(self.folder_sizes),
                        dict(self.file_sizes),
                        dict(self.file_types)
                    )

        thread = threading.Thread(target=_scan_worker, daemon=True)
        thread.start()
        return thread
