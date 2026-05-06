import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.ttk as ttk
import tkinter as tk
import tkinter.font as tkfont
import os
from scanner import DiskScanner
from chart import build_pie_chart_from_dict
from export import export_to_csv


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    return f"{size_bytes} Б"


class CustomContextMenu(ctk.CTkToplevel):
    def __init__(self, parent, command=None):
        super().__init__(parent)
        self.parent = parent
        self.command = command
        self.overrideredirect(True)
        self.withdraw()
        self._active = False
        self._id = str(self)

        self.border_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#555555")
        self.border_frame.pack(padx=0, pady=0)

        self.inner_frame = ctk.CTkFrame(
            self.border_frame, corner_radius=0, fg_color="#2b2b2b")
        self.inner_frame.pack(padx=1, pady=1)

        self.btn = ctk.CTkButton(
            self.inner_frame,
            text="📂 Открыть расположение",
            command=self._on_click,
            fg_color="#2b2b2b",
            hover_color="#1a5fb4",
            text_color="white",
            font=("Segoe UI", 13),
            corner_radius=0,
            width=180,
            height=20
        )
        self.btn.pack(fill="both", expand=True, padx=2, pady=2)

    def show(self, x, y):
        if self._active:
            return

        self._active = True
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()

        self.parent.bind_all("<Button-1>", self._on_global_click, add="+")

    def hide(self):
        if not self._active:
            return

        self._active = False
        self.withdraw()

    def _on_click(self):
        cmd = self.command
        self.hide()
        if cmd:
            self.parent.after(50, cmd)

    def _on_global_click(self, event):
        if not self._active:
            return

        widget = event.widget

        while widget:
            if widget == self:
                return
            widget = widget.master

        self.hide()


class ToolTip:
    """
    Простая всплывающая подсказка для любого виджета.
    Принимает функцию textfunc, которая должна возвращать строку или None.
    """

    def __init__(self, widget, textfunc, delay=500):
        self.widget = widget
        self.textfunc = textfunc
        self.delay = delay
        self.tipwindow = None
        self.id = None
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self):
        text = self.textfunc()
        if not text:
            return
        self.hidetip()
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (
            self.widget.winfo_rootx() + 10,
            self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        ))
        label = tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 10)
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class ProgressWindow(ctk.CTkToplevel):
    def __init__(self, parent, scanner, on_complete):
        super().__init__(parent)
        self.scanner = scanner
        self.parent = parent
        self.on_complete = on_complete
        self._cancelled = False

        self.title("Сканирование...")
        self.geometry("400x180")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 150) // 2
        self.geometry(f"+{x}+{y}")

        self.label = ctk.CTkLabel(
            self, text="Выполняется сканирование...", font=("Segoe UI", 14, "bold"))
        self.label.pack(pady=(20, 10))

        self.progress = ctk.CTkProgressBar(self, width=350)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.percent_label = ctk.CTkLabel(
            self, text=" 0% (0/0) ", font=("Segoe UI", 12))
        self.percent_label.pack(pady=10)

        self.cancel_btn = ctk.CTkButton(
            self, text="Отмена", command=self._cancel,  fg_color="#c0392b", hover_color="#e74c3c", width=100)
        self.cancel_btn.pack(pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.scanner.progress_callback = self._update_progress
        self.scanner.done_callback = self._on_scan_done

    def _update_progress(self, current, total):
        if self._cancelled or not self.winfo_exists():
            return

        if total > 0:
            fraction = current / total
            percent = int(fraction * 100)
            self.after(0, lambda: self._safe_update(
                fraction, percent, current, total))

    def _safe_update(self, fraction, percent, current, total):
        if not self.winfo_exists():
            return
        try:
            self.progress.set(fraction)
            self.percent_label.configure(
                text=f" {percent}% ({current}/{total}) ")
        except Exception:
            pass

    def _on_scan_done(self, folder_sizes, file_sizes, file_types):
        if self._cancelled or not self.winfo_exists():
            return
        self.after(0, lambda: self._safe_done(
            folder_sizes, file_sizes, file_types))

    def _safe_done(self, folder_sizes, file_sizes, file_types):
        try:
            if self.on_complete:
                self.on_complete(folder_sizes, file_sizes, file_types)
        except Exception:
            pass
        finally:
            self._cleanup_and_destroy()

    def _cancel(self):
        self._cancelled = True
        self.scanner.stop()
        self.scanner.done_callback = None
        if self.on_complete:
            self.parent.after(0, lambda: self.on_complete({}, {}, {}))
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        self.scanner.progress_callback = None
        self.scanner.done_callback = None
        self.withdraw()
        self.update_idletasks()
        if self.winfo_exists():
            try:
                self.grab_release()
            except Exception:
                pass
            try:
                self.destroy()
            except Exception:
                pass


class DiskAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Диск-анализатор")
        self.geometry("1200x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.scanner = DiskScanner()
        self.scan_thread = None
        self.folder_sizes = {}
        self.file_sizes = {}
        self.file_types = {}
        self.selected_path = None
        self.full_selected_path = ""

        self.tree_cache = {}
        self._closing = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill="x", padx=10, pady=10)

        self.path_label = ctk.CTkLabel(
            self.top_frame, text="Папка: не выбрана", anchor="w", width=400)
        self.path_label.pack(side="left", padx=5)

        self.browse_btn = ctk.CTkButton(
            self.top_frame, text="Обзор", command=self._browse_folder, width=80)
        self.browse_btn.pack(side="left", padx=5)

        self.scan_btn = ctk.CTkButton(
            self.top_frame, text="Сканировать", command=self._start_scan, width=100, state="disabled")
        self.scan_btn.pack(side="left", padx=5)

        self.export_btn = ctk.CTkButton(
            self.top_frame, text="Экспорт CSV", command=self._export_csv, width=100, state="disabled")
        self.export_btn.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(
            self.top_frame, text="Готов", text_color="gray")
        self.status_label.pack(side="right", padx=10)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.paned = tk.PanedWindow(
            self.main_frame,
            orient=tk.HORIZONTAL,
            sashwidth=12,
            bg="#242424"
        )
        self.paned.pack(fill="both", expand=True)

        self.left_wrapper = ctk.CTkFrame(self.paned, fg_color="#242424")

        self.left_frame = ctk.CTkFrame(
            self.left_wrapper,
            fg_color="#333333"
        )
        self.left_frame.pack(fill="both", expand=True, pady=2)

        self.tree_label = ctk.CTkLabel(
            self.left_frame,
            text="Дерево папок и файлов:",
            font=("Segoe UI", 14, "bold")
        )
        self.tree_label.pack(anchor="w", padx=10, pady=5)

        self.path_info_frame = ctk.CTkFrame(self.left_frame)
        self.path_info_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.path_info_label = ctk.CTkLabel(
            self.path_info_frame,
            text="Путь: ",
            anchor="w",
            font=("Segoe UI", 12)
        )
        self.path_info_label.pack(side="left", padx=(5, 0), pady=2)

        self.path_info_value = ctk.CTkLabel(
            self.path_info_frame,
            text="",
            anchor="w",
            font=("Segoe UI", 12, "bold"),
            text_color="#4fc3f7"
        )
        self.path_info_value.pack(
            side="left", padx=5, pady=2, fill="x", expand=True)

        self.path_tooltip = ToolTip(
            self.path_info_value,
            lambda: self.full_selected_path if self.full_selected_path else None
        )

        self.copy_path_btn = ctk.CTkButton(
            self.path_info_frame,
            text="📋",
            command=self._copy_path_to_clipboard,
            width=30,
            height=30,
            font=("Segoe UI", 16)
        )
        self.copy_path_btn.pack(side="right", padx=5, pady=2)

        self.bind("<Configure>", lambda e: self._refresh_path_display())

        self.tree_container = ctk.CTkFrame(self.left_frame)
        self.tree_container.pack(
            fill="both", expand=True, padx=10, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background="#2b2b2b",
                        foreground="white",
                        fieldbackground="#2b2b2b",
                        rowheight=25,
                        font=("Segoe UI", 10),
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#2b2b2b",
                        foreground="white",
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=1)
        style.map("Treeview.Heading",
                  background=[("active", "#2b2b2b")],
                  foreground=[("active", "#ffffff")])
        style.map("Treeview",
                  background=[("selected", "#1a5fb4")],
                  foreground=[("selected", "white")])

        self.tree = ttk.Treeview(
            self.tree_container,
            columns=("size", "percent"),
            show="tree headings",
            selectmode="browse"
        )

        self.tree.heading("#0", text="Имя", anchor="w")
        self.tree.heading("size", text="Размер", anchor="e")
        self.tree.heading("percent", text="%", anchor="e")

        self.tree.column("#0", width=450, minwidth=200)
        self.tree.column("size", width=80, minwidth=80, anchor="e")
        self.tree.column("percent", width=80, minwidth=60, anchor="e")

        self.tree.tag_configure("folder", foreground="#4fc3f7")
        self.tree.tag_configure("virtual_folder", foreground="#ffd700")
        self.tree.tag_configure("file", foreground="#a5d6a7")

        self.tree_scroll_y = ctk.CTkScrollbar(
            self.tree_container, width=10, orientation="vertical")
        self.tree_scroll_y.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self.tree_scroll_y.set)
        self.tree_scroll_y.configure(command=self.tree.yview)

        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = CustomContextMenu(
            self, command=self._open_file_location)

        self.right_wrapper = ctk.CTkFrame(self.paned, fg_color="#242424")

        self.right_frame = ctk.CTkFrame(
            self.right_wrapper,
            fg_color="#333333"
        )
        self.right_frame.pack(fill="both", expand=True, pady=2)

        self.chart_label = ctk.CTkLabel(
            self.right_frame,
            text="Круговая диаграмма:",
            font=("Segoe UI", 14, "bold")
        )
        self.chart_label.pack(anchor="w", padx=10, pady=5)

        self.chart_container = ctk.CTkFrame(self.right_frame)
        self.chart_container.pack(
            fill="both", expand=True, padx=10, pady=(0, 10))

        self.paned.add(self.left_wrapper, minsize=300)
        self.paned.add(self.right_wrapper, minsize=300)

        self.types_frame = ctk.CTkFrame(self)
        self.types_frame.pack(fill="x", padx=10, pady=(0, 10), side="bottom")

        self.types_label = ctk.CTkLabel(
            self.types_frame,
            text="По типам файлов:",
            font=("Segoe UI", 12, "bold")
        )
        self.types_label.pack(side="left", padx=10, pady=5)

        self.types_text = ctk.CTkLabel(
            self.types_frame,
            text="Ожидание сканирования...",
            font=("Consolas", 11)
        )
        self.types_text.pack(side="left", padx=10, pady=5)

    def _refresh_path_display(self):
        path = self.full_selected_path
        if path:
            self.path_info_value.configure(
                text=self.shorten_path_dynamic(path)
            )

    def _browse_folder(self):
        folder = fd.askdirectory(title="Выберите папку или диск")
        if folder:
            self.path_label.configure(text=f"Папка: {folder}")
            self.selected_path = folder
            self.scan_btn.configure(state="normal")

    def _start_scan(self):
        if not self.selected_path:
            return

        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self.status_label.configure(
            text="Сканирование...", text_color="#f39c12")

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.types_text.configure(text="Сканирование...")
        for widget in self.chart_container.winfo_children():
            widget.destroy()
        self.tree_cache.clear()
        self.path_info_value.configure(text="")

        self.progress_window = ProgressWindow(
            self, self.scanner, self._on_scan_complete)
        self.scan_thread = self.scanner.scan(self.selected_path)

    def _on_scan_complete(self, folder_sizes, file_sizes, file_types):
        self.scan_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.export_btn.configure(state="normal")

        if not folder_sizes and not file_sizes:
            self.status_label.configure(text="Отменено", text_color="#e74c3c")
            self.types_text.configure(text="Сканирование отменено")
            return

        self.folder_sizes = folder_sizes
        self.file_sizes = file_sizes
        self.file_types = file_types

        self.status_label.configure(text="Готово", text_color="#2ecc71")

        if not self.folder_sizes and not self.file_sizes:
            self.status_label.configure(
                text="Нет данных", text_color="#e74c3c")
            return

        root_norm = os.path.normpath(self.selected_path)

        total_size = self.folder_sizes.get(self.selected_path, 0)
        if total_size == 0:
            total_size = self.folder_sizes.get(root_norm, 0)
        if total_size == 0:
            total_size = sum(self.file_types.values())

        self._build_tree_cache()

        for item in self.tree.get_children():
            self.tree.delete(item)

        if root_norm in self.tree_cache:
            self._populate_children("", root_norm, total_size)
        else:
            self.tree.insert("", "end", text="Нет данных",
                             values=("0 Б", "0%"))

        types_lines = []
        for ftype, size in self.file_types.items():
            types_lines.append(f"{ftype}: {format_size(size)}")
        self.types_text.configure(text="  |  ".join(types_lines))

        if root_norm in self.tree_cache:
            folders = self.tree_cache[root_norm]["folders"]
            top8 = folders[:8]

            chart_data = {}
            for path, size, etype in top8:
                name = os.path.basename(
                    path) if os.path.basename(path) else path
                chart_data[f"📁 {name}"] = size

            other_size = total_size - sum(size for _, size, _ in top8)
            if other_size > 0:
                chart_data["Прочее"] = max(0, other_size)
        else:
            chart_data = {"Все данные": total_size}

        for widget in self.chart_container.winfo_children():
            widget.destroy()

        if chart_data:
            canvas = build_pie_chart_from_dict(
                self.chart_container, chart_data, scan_path=self.selected_path)
            canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_tree_cache(self):
        self.tree_cache.clear()
        root_norm = os.path.normpath(self.selected_path)

        for path in self.folder_sizes:
            path_norm = os.path.normpath(path)
            if path_norm == root_norm:
                continue

            parent = os.path.dirname(path_norm)
            parent_norm = os.path.normpath(parent)

            if parent_norm not in self.tree_cache:
                self.tree_cache[parent_norm] = {"folders": [], "files": []}

            entry = (path, self.folder_sizes[path], "folder")
            if entry not in self.tree_cache[parent_norm]["folders"]:
                self.tree_cache[parent_norm]["folders"].append(entry)

        for filepath, size in self.file_sizes.items():
            file_norm = os.path.normpath(filepath)
            parent = os.path.dirname(file_norm)
            parent_norm = os.path.normpath(parent)

            if parent_norm not in self.tree_cache:
                self.tree_cache[parent_norm] = {"folders": [], "files": []}

            entry = (filepath, size, "file")
            self.tree_cache[parent_norm]["files"].append(entry)

        for parent in self.tree_cache:
            self.tree_cache[parent]["folders"].sort(
                key=lambda x: x[1], reverse=True)
            self.tree_cache[parent]["files"].sort(
                key=lambda x: x[1], reverse=True)

    def _populate_children(self, parent_id, parent_path_norm, parent_size):
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
                name = os.path.basename(
                    path) if os.path.basename(path) else path
                path_norm = os.path.normpath(path)
                has_children = path_norm in self.tree_cache

                child_id = self.tree.insert(
                    parent_id, "end",
                    text=f"📁 {name}",
                    values=(format_size(size), percent_str),
                    open=False,
                    tags=("folder",)
                )

                self.tree.item(child_id, tags=(path_norm, "folder"))

                if has_children:
                    self.tree.insert(child_id, "end", text="загрузка...")

            elif entry_type == "virtual_folder":
                files_list = data
                virtual_path = parent_path_norm + os.sep + "<файлы>"

                files_folder_id = self.tree.insert(
                    parent_id, "end",
                    text=f"📁 <файлы> ({len(files_list)} шт.)",
                    values=(format_size(size), percent_str),
                    open=False,
                    tags=("virtual_folder",)
                )

                self.tree.item(files_folder_id, tags=(
                    virtual_path, "virtual_folder"))

                self.tree.insert(files_folder_id, "end", text="загрузка...")

    def _populate_files(self, parent_id, parent_path_norm, files_parent_size):
        real_parent = parent_path_norm.rsplit(os.sep + "<файлы>", 1)[0]

        if real_parent not in self.tree_cache:
            return

        files = self.tree_cache[real_parent]["files"]

        for entry in files:
            path, size, etype = entry
            name = os.path.basename(path) if os.path.basename(path) else path

            if files_parent_size > 0:
                percent = (size / files_parent_size) * 100
                percent_str = f"{percent:.1f}%"
            else:
                percent_str = "0%"

            file_id = self.tree.insert(
                parent_id, "end",
                text=f"📄 {name}",
                values=(format_size(size), percent_str),
                open=False,
                tags=("file",)
            )

            self.tree.item(file_id, tags=(path, "file"))

    def shorten_path_dynamic(self, path: str) -> str:
        if not path:
            return path

        path = os.path.normpath(path)

        font = tkfont.Font(font=self.path_info_value.cget("font"))
        max_width = int(self.path_info_value.winfo_width() * 1.35)

        if max_width <= 10:
            return path

        parts = path.split(os.sep)
        if len(parts) <= 3:
            return path

        def build(l, r):
            left_part = os.sep.join(l)
            right_part = os.sep.join(r)

            if l and r:
                return f"{left_part}{os.sep}...{os.sep}{right_part}"
            elif l:
                return left_part
            elif r:
                return right_part
            return ""

        def fits(text: str) -> bool:
            return font.measure(text) <= max_width

        full = os.sep.join(parts)
        if fits(full):
            return full

        left = 1
        right = 1

        best = build(parts[:left], parts[-right:])

        while left + right < len(parts):
            if left < len(parts) - right:
                candidate = build(parts[:left + 1], parts[-right:])
                if fits(candidate):
                    left += 1
                    best = candidate
                    continue

            if right < len(parts) - left:
                candidate = build(parts[:left], parts[-(right + 1):])
                if fits(candidate):
                    right += 1
                    best = candidate
                    continue

            break

        return best

    def _on_tree_select(self, event):
        item_id = self.tree.focus()
        if not item_id:
            self.path_info_value.configure(text="")
            return

        tags = self.tree.item(item_id, "tags")
        if not tags:
            self.path_info_value.configure(text="")
            return

        item_type = tags[1] if len(tags) > 1 else ""
        path = tags[0]

        if item_type == "virtual_folder":
            real_path = path.rsplit(os.sep + "<файлы>", 1)[0]
            self.full_selected_path = real_path
            self.path_info_value.configure(
                text=self.shorten_path_dynamic(real_path))
        elif item_type in ("folder", "file"):
            self.full_selected_path = path
            self.path_info_value.configure(
                text=self.shorten_path_dynamic(path))
        else:
            self.full_selected_path = ""
            self.path_info_value.configure(text="")

    def _on_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self._on_tree_select(None)

            tags = self.tree.item(item_id, "tags")
            if tags and len(tags) > 1 and tags[1] in ("folder", "file", "virtual_folder"):
                self.context_menu.show(event.x_root, event.y_root)

    def _open_file_location(self):
        item_id = self.tree.focus()
        if not item_id:
            return

        tags = self.tree.item(item_id, "tags")
        if not tags or len(tags) < 2:
            return

        item_type = tags[1]
        path = tags[0]

        if item_type == "virtual_folder":
            if path.endswith(os.sep + "<файлы>"):
                path = path[:-len(os.sep + "<файлы>")]
            elif path.endswith("/<файлы>"):
                path = path[:-len("/<файлы>")]

        if not path or not os.path.exists(path):
            return

        if item_type == "file":
            folder = os.path.dirname(path)
            if os.path.exists(folder):
                os.startfile(folder)
        else:
            os.startfile(path)

    def _on_tree_open(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return

        tags = self.tree.item(item_id, "tags")
        if not tags or len(tags) < 2:
            return

        item_type = tags[1]

        if item_type not in ("folder", "virtual_folder"):
            return

        path_norm = tags[0]

        children = self.tree.get_children(item_id)
        if children:
            first_child_text = self.tree.item(children[0], "text")
            if first_child_text != "загрузка...":
                return

        for child in children:
            self.tree.delete(child)

        if item_type == "folder":
            parent_size = self.folder_sizes.get(path_norm, 0)
            if parent_size == 0:
                for orig_path, size in self.folder_sizes.items():
                    if os.path.normpath(orig_path) == path_norm:
                        parent_size = size
                        break

            self._populate_children(item_id, path_norm, parent_size)

        elif item_type == "virtual_folder":
            real_parent = path_norm.rsplit(os.sep + "<файлы>", 1)[0]

            if real_parent in self.tree_cache:
                files = self.tree_cache[real_parent]["files"]
                files_total_size = sum(size for _, size, _ in files)
                self._populate_files(item_id, path_norm, files_total_size)

    def _copy_path_to_clipboard(self):
        path = self.full_selected_path
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            self.copy_path_btn.configure(text="✓")
            self.after(1000, lambda: self.copy_path_btn.configure(text="📋"))

    def _export_csv(self):
        if not self.folder_sizes:
            return

        filepath = export_to_csv(self.folder_sizes, self.file_types)
        self.status_label.configure(
            text=f"Сохранено: {os.path.basename(filepath)}", text_color="#2ecc71")

    def _on_close(self):
        if self._closing:
            return
        self._closing = True

        self.scanner.stop()

        for attr in ['progress_window', 'context_menu']:
            window = getattr(self, attr, None)
            if window:
                try:
                    if window.winfo_exists():
                        window.destroy()
                except Exception:
                    pass

        try:
            for task in self.tk.call('after', 'info'):
                self.after_cancel(task)
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

        os._exit(0)


def report_callback_exception(exc, val, tb):
    msg = str(val)
    if "application has been destroyed" in msg or "invalid command name" in msg or "can't delete Tcl command" in msg:
        return
    import traceback
    traceback.print_exception(exc, val, tb)


tk.Tk.report_callback_exception = report_callback_exception
tk.Toplevel.report_callback_exception = report_callback_exception

if __name__ == "__main__":
    app = DiskAnalyzerApp()
    app.mainloop()
