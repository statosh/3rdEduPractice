import csv
import os
import sys
from datetime import datetime


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    return f"{size_bytes} Б"


def get_app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def export_to_csv(folder_sizes: dict, file_sizes: dict, file_types: dict, root_path: str, filename: str = None):
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"disk_analysis_{timestamp}.csv"

    save_dir = get_app_dir()
    filepath = os.path.join(save_dir, filename)

    root_norm = os.path.normpath(root_path)

    root_folders = {}
    for path, size in folder_sizes.items():
        path_norm = os.path.normpath(path)
        parent = os.path.normpath(os.path.dirname(path_norm))
        if parent == root_norm:
            root_folders[path] = size

    root_files = {}
    for path, size in file_sizes.items():
        path_norm = os.path.normpath(path)
        parent = os.path.normpath(os.path.dirname(path_norm))
        if parent == root_norm:
            root_files[path] = size

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")

        writer.writerow(["Папка", "Размер (байт)", "Размер"])
        for path, size in sorted(root_folders.items(), key=lambda x: x[1], reverse=True):
            name = os.path.basename(path) if os.path.basename(path) else path
            writer.writerow([name, size, format_size(size)])

        writer.writerow([])

        writer.writerow(["Файл", "Размер (байт)", "Размер"])
        for path, size in sorted(root_files.items(), key=lambda x: x[1], reverse=True):
            name = os.path.basename(path) if os.path.basename(path) else path
            writer.writerow([name, size, format_size(size)])

        writer.writerow([])

        writer.writerow(["Тип", "Размер (байт)", "Размер"])
        for ftype, size in file_types.items():
            writer.writerow([ftype, size, format_size(size)])

    return filepath
