import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os

matplotlib.use("TkAgg")


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    return f"{size_bytes} Б"


def build_pie_chart_from_dict(parent_frame, data: dict, scan_path: str = ""):
    plt.clf()
    plt.close('all')

    plt.style.use("dark_background")

    labels = list(data.keys())
    sizes = list(data.values())
    total = sum(sizes)

    clean_labels = []
    for label in labels:
        clean = label.replace("📁 ", "").replace(
            "📄 ", "").replace("📁", "").replace("📄", "")
        clean_labels.append(clean)

    paired = list(zip(labels, clean_labels, sizes))
    paired.sort(key=lambda x: x[2], reverse=True)

    labels = [p[0] for p in paired]
    clean_labels = [p[1] for p in paired]
    sizes = [p[2] for p in paired]

    fig, (ax, ax_legend) = plt.subplots(
        2, 1,
        figsize=(6, 7),
        dpi=100,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    ax_legend.set_facecolor("#1e1e1e")

    colors = plt.cm.Set3(range(len(labels)))
    percentages = [(s / total * 100) for s in sizes]

    def autopct_filter(pct):
        return f'{pct:.1f}%' if pct >= 4.5 else ''

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=autopct_filter,
        colors=colors,
        startangle=90,
        pctdistance=0.75,
        explode=[0.03] * len(labels)
    )

    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_color("white")
        autotext.set_fontweight('bold')

    legend_labels = []
    for label, size, pct in zip(clean_labels, sizes, percentages):
        legend_labels.append(f"{label} ({format_size(size)}) — {pct:.1f}%")

    ax_legend.axis("off")

    ax_legend.legend(
        wedges,
        legend_labels,
        loc="center",
        fontsize=8,
        frameon=False,
        ncol=1
    )

    total_str = format_size(total)

    if scan_path:
        folder_name = os.path.basename(scan_path.rstrip("/\\")) or scan_path
        title = f"{folder_name}\n(всего: {total_str})"
    else:
        title = f"Распределение места\n(всего: {total_str})"

    ax.set_title(title, fontsize=11, fontweight='bold', color="white")

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    return canvas
