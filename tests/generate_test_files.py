import os
import random

def generate_test_files(root_path: str, num_files: int = 100_000):
    extensions = ['.txt', '.jpg', '.png', '.pdf', '.docx', '.mp4', '.avi', '.mkv', '.py', '.json']
    
    os.makedirs(root_path, exist_ok=True)
    
    num_folders = 20
    for i in range(num_folders):
        folder = os.path.join(root_path, f"folder_{i:04d}")
        os.makedirs(folder, exist_ok=True)
    
    print(f"Генерация {num_files} тестовых файлов в {root_path}...")
    
    for i in range(num_files):
        folder_idx = i % num_folders
        folder = os.path.join(root_path, f"folder_{folder_idx:04d}")
        
        ext = random.choice(extensions)
        filename = f"file_{i:06d}{ext}"
        filepath = os.path.join(folder, filename)
        
        size = random.randint(1024, 102400)
        with open(filepath, 'wb') as f:
            f.write(os.urandom(size))
        
        if (i + 1) % 10000 == 0:
            print(f"  Создано {i + 1} файлов...")
    
    print(f"Готово! Создано {num_files} файлов")

if __name__ == "__main__":
    test_path = r""
    generate_test_files(test_path, 100_000)