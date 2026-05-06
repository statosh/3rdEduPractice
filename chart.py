import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
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

    bg = "#333333"
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax_legend.set_facecolor(bg)

    colors = [
        "#4fc3f7",
        "#81c784",
        "#ffb74d",
        "#ba68c8",
        "#e57373",
        "#64b5f6",
        "#aed581",
        "#ff8a65",
        "#9575cd",
        "#f06292",
    ]

    colors = colors[:len(labels)]
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
        autotext.set_path_effects([
            pe.withStroke(linewidth=2, foreground='black')
        ])

    legend_labels = []
    for label, size, pct in zip(clean_labels, sizes, percentages):
        legend_labels.append(f"{label} ({format_size(size)}) — {pct:.1f}%")

    ax_legend.axis("off")

    legend = ax_legend.legend(
        wedges,
        legend_labels,
        loc="center",
        fontsize=8,
        frameon=False,
        ncol=1
    )

    for text in legend.get_texts():
        text.set_color("white")
        text.set_path_effects([
            pe.withStroke(linewidth=2, foreground='black')
        ])

    total_str = format_size(total)

    if scan_path:
        folder_name = os.path.basename(scan_path.rstrip("/\\")) or scan_path
        title = f"{folder_name}\n(всего: {total_str})"
    else:
        title = f"Распределение места\n(всего: {total_str})"

    title_obj = ax.set_title(
        title,
        fontsize=11,
        fontweight='bold',
        color="white",
        pad=10
    )

    title_obj.set_path_effects([
        pe.withStroke(linewidth=2, foreground='black')
    ])

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    return canvas
