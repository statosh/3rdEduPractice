import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QSizePolicy
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('QtAgg')


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    return f"{size_bytes} Б"


def _get_theme_colors(is_dark: bool) -> dict:
    if is_dark:
        return {
            "bg": "#1e1e2e",
            "fg": "#cdd6f4",
            "stroke": "#1e1e2e",
            "plot_bg": "#1e1e2e",
            "pie_colors": [
                "#4fc3f7", "#81c784", "#ffb74d", "#ba68c8", "#e57373",
                "#64b5f6", "#aed581", "#ff8a65", "#9575cd", "#f06292",
            ]
        }
    else:
        return {
            "bg": "#ffffff",
            "fg": "#333333",
            "stroke": "#ffffff",
            "plot_bg": "#ffffff",
            "pie_colors": [
                "#1976d2", "#388e3c", "#f57c00", "#7b1fa2", "#d32f2f",
                "#0288d1", "#689f38", "#e64a19", "#512da8", "#c2185b",
            ]
        }


class ResizableChartCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.chart_data = {}
        self.scan_path = ""
        self.is_dark = True

        fig = Figure(figsize=(6, 7), dpi=100)
        super().__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 300)
        self.updateGeometry()

        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)

    def set_chart_data(self, data: dict, scan_path: str, is_dark: bool):
        self.chart_data = data
        self.scan_path = scan_path
        self.is_dark = is_dark
        self._redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.chart_data:
            self._redraw()

    def _redraw(self):
        if not self.chart_data:
            return

        theme = _get_theme_colors(self.is_dark)

        width_px = self.width()
        height_px = self.height()

        if width_px <= 0 or height_px <= 0:
            return

        dpi = self.figure.dpi
        fig_width = width_px / dpi
        fig_height = height_px / dpi

        self.figure.clear()
        self.figure.set_size_inches(fig_width, fig_height)
        self.figure.patch.set_facecolor(theme["bg"])

        base_font = max(6, min(12, height_px / 55))
        title_font = base_font * 1.3
        legend_font = base_font * 0.9

        labels = list(self.chart_data.keys())
        sizes = list(self.chart_data.values())
        total = sum(sizes)

        clean_labels = [label.replace("📁 ", "").replace("📄 ", "").replace(
            "📁", "").replace("📄", "") for label in labels]

        paired = list(zip(labels, clean_labels, sizes))
        paired.sort(key=lambda x: x[2], reverse=True)

        labels = [p[0] for p in paired]
        clean_labels = [p[1] for p in paired]
        sizes = [p[2] for p in paired]

        ax_pie = self.figure.add_axes([0.05, 0.28, 0.9, 0.65])
        ax_pie.set_facecolor(theme["plot_bg"])

        ax_legend = self.figure.add_axes([0.05, 0.02, 0.9, 0.24])
        ax_legend.set_facecolor(theme["plot_bg"])
        ax_legend.axis("off")

        colors = theme["pie_colors"][:len(labels)]

        def autopct_filter(pct):
            return f'{pct:.1f}%' if pct >= 5 else ''

        wedges, texts, autotexts = ax_pie.pie(
            sizes,
            labels=None,
            autopct=autopct_filter,
            colors=colors,
            startangle=90,
            pctdistance=0.75,
            explode=[0.03] * len(labels),
            radius=1.0
        )

        for autotext in autotexts:
            autotext.set_fontsize(base_font * 0.9)
            autotext.set_color(theme["fg"])
            autotext.set_fontweight('bold')
            autotext.set_path_effects([
                pe.withStroke(linewidth=2, foreground=theme["stroke"])
            ])

        legend_labels = []
        for label, size in zip(clean_labels, sizes):
            pct = (size / total * 100) if total > 0 else 0
            legend_labels.append(f"{label} — {format_size(size)} ({pct:.1f}%)")

        legend = ax_legend.legend(
            wedges,
            legend_labels,
            loc="upper left",
            bbox_to_anchor=(0, 1),
            fontsize=legend_font,
            frameon=False,
            ncol=1,
            handlelength=1.0,
            handletextpad=0.5,
            borderpad=0,
            labelspacing=0.15
        )

        for text in legend.get_texts():
            text.set_color(theme["fg"])
            text.set_path_effects([
                pe.withStroke(linewidth=1.5, foreground=theme["stroke"])
            ])

        total_str = format_size(total)

        if self.scan_path:
            folder_name = os.path.basename(
                self.scan_path.rstrip("/\\")) or self.scan_path
            title = f"{folder_name}\n(всего: {total_str})"
        else:
            title = f"Распределение места\n(всего: {total_str})"

        self.figure.suptitle(
            title,
            fontsize=title_font,
            fontweight='bold',
            color=theme["fg"],
            y=0.96,
            va="top"
        )

        self.figure.subplots_adjust(
            top=0.85, bottom=0.02, left=0.02, right=0.98)

        self.draw_idle()


def build_pie_chart(parent_widget, data: dict, scan_path: str = "", is_dark: bool = True):
    plt.clf()
    plt.close('all')

    canvas = ResizableChartCanvas(parent_widget)
    canvas.set_chart_data(data, scan_path, is_dark)

    return canvas
