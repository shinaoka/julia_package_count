from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from julia_package_count.registry import RollingPackageCount, Snapshot

# Artifacts are generated headlessly; avoid needing a display or an X connection.
matplotlib.use("Agg")

STYLE = {
    "font.family": "DejaVu Sans",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#222222",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "text.color": "#222222",
    "axes.titleweight": "bold",
}


def write_rolling_chart(
    rows: list[RollingPackageCount], output_stem: Path
) -> list[Path]:
    if not rows:
        raise ValueError("rows must not be empty")

    months = [datetime.fromisoformat(row.month) for row in rows]
    released = [row.released_last_12m for row in rows]
    registered = [row.registered for row in rows]

    plt.rcParams.update(STYLE)

    fig, ax = plt.subplots(figsize=(12, 6.4), dpi=180)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.8, bottom=0.16)

    fig.text(
        0.085,
        0.955,
        "Julia General registry: packages released in the last 12 months",
        fontsize=21,
        fontweight="bold",
        ha="left",
        va="top",
    )
    fig.text(
        0.085,
        0.912,
        "Non-JLL packages; a package counts when a version entry was added in the previous "
        "365 days.",
        fontsize=10.5,
        color="#666666",
        ha="left",
        va="top",
    )

    ax.plot(
        months,
        registered,
        color="#B0B7BF",
        linewidth=2.2,
        label="registered non-JLL packages",
    )
    ax.plot(
        months,
        released,
        color="#0072B2",
        linewidth=2.8,
        marker="o",
        markersize=2.5,
        label="packages released in the last 12 months",
    )
    ax.set_ylabel("Packages")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/1/1"))
    ax.grid(color="#e6e8eb", linewidth=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")

    fig.text(
        0.085,
        0.045,
        "Source: JuliaRegistries/General. The first point is "
        f"{rows[0].month}, the first month with a full 12-month window.",
        fontsize=9,
        color="#666666",
        ha="left",
    )
    fig.text(
        0.085,
        0.014,
        f"The last point is {rows[-1].month}, so its window ends before the registry head.",
        fontsize=9,
        color="#666666",
        ha="left",
    )

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    paths = [output_stem.with_suffix(ext) for ext in [".png", ".pdf", ".svg"]]
    for path in paths:
        fig.savefig(path)
    plt.close(fig)
    return paths


def write_chart(
    snapshots: list[Snapshot],
    growth: list[tuple[str, int]],
    output_stem: Path,
) -> list[Path]:
    if not snapshots:
        raise ValueError("snapshots must not be empty")

    labels = [snapshot.label for snapshot in snapshots]
    counts = [snapshot.non_jll for snapshot in snapshots]
    growth_labels = [label for label, _ in growth]
    growth_values = [value for _, value in growth]

    plt.rcParams.update(STYLE)

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 8.7),
        dpi=180,
        gridspec_kw={"height_ratios": [2.35, 1.30]},
    )
    fig.subplots_adjust(left=0.085, right=0.985, top=0.79, bottom=0.15, hspace=0.54)

    fig.text(
        0.085,
        0.955,
        "Julia General registry package count, JLL excluded",
        fontsize=21,
        fontweight="bold",
        ha="left",
        va="top",
    )
    fig.text(
        0.085,
        0.912,
        "2017* is 2017-08-29, the first non-empty General commit. Snapshot points after that are Jan 1 states.",
        fontsize=10.5,
        color="#666666",
        ha="left",
        va="top",
    )
    fig.text(
        0.085,
        0.885,
        "Lower bars label the year in which the increase occurred; 2017 partial covers 2017-08-29 to 2018-01-01.",
        fontsize=10.5,
        color="#666666",
        ha="left",
        va="top",
    )

    x = list(range(len(labels)))
    ax1.plot(
        x,
        counts,
        color="#0072B2",
        linewidth=2.8,
        marker="o",
        markersize=6.5,
        markerfacecolor="#D55E00",
        markeredgecolor="white",
        markeredgewidth=1.4,
    )
    ax1.set_title("Non-JLL package count at snapshot", loc="left", fontsize=13, pad=10)
    ax1.set_ylabel("Packages")
    ax1.set_xticks(x, labels)
    ax1.set_ylim(0, max(12000, int(max(counts) * 1.1)))
    ax1.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax1.grid(axis="y", color="#e6e8eb", linewidth=0.9)
    ax1.spines[["top", "right"]].set_visible(False)

    for index, count in enumerate(counts):
        ax1.annotate(
            f"{count:,}",
            (index, count),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8.5,
        )

    bar_x = list(range(len(growth_labels)))
    ax2.bar(
        bar_x,
        growth_values,
        width=0.64,
        color="#56B4E9",
        edgecolor="#1f6d8f",
        linewidth=0.8,
    )
    ax2.set_title("Non-JLL package increase by year", loc="left", fontsize=13, pad=10)
    ax2.set_ylabel("Increase")
    ax2.set_xticks(bar_x, growth_labels)
    ax2.set_ylim(0, max(2000, int(max(growth_values) * 1.18) if growth_values else 1))
    ax2.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    ax2.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax2.grid(axis="y", color="#e6e8eb", linewidth=0.9)
    ax2.spines[["top", "right"]].set_visible(False)

    for index, value in enumerate(growth_values):
        ax2.annotate(
            f"+{value:,}",
            (index, value),
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
            fontsize=8.5,
        )

    fig.text(
        0.085,
        0.057,
        "Source: JuliaRegistries/General. Root [Pp]ackage.toml entries counted; *_jll and jll/ subtree excluded.",
        fontsize=9.2,
        color="#666666",
        ha="left",
    )

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    paths = [output_stem.with_suffix(ext) for ext in [".png", ".pdf", ".svg"]]
    for path in paths:
        fig.savefig(path)
    plt.close(fig)
    return paths
