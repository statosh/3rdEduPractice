# export.py
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


def export_to_csv(folder_sizes: dict, file_types: dict, filename: str = None):
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"disk_analysis_{timestamp}.csv"
    
    save_dir = get_app_dir()
    filepath = os.path.join(save_dir, filename)
    
    sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)[:10]
    
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        
        writer.writerow(["Топ-10 папок по размеру"])
        writer.writerow(["Папка", "Размер (байт)", "Размер"])
        for path, size in sorted_folders:
            writer.writerow([path, size, format_size(size)])
        
        writer.writerow([])
        writer.writerow(["Распределение по типам файлов"])
        writer.writerow(["Тип", "Размер (байт)", "Размер"])
        for ftype, size in file_types.items():
            writer.writerow([ftype, size, format_size(size)])
    
    return filepath