"""
Build STRtree cho layer parcel/road trong data/full_ID_HBC.gdb.
"""
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pyogrio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from sil.geometric import Envelope
from sil.base import Item
from sil.core.strtree import STRtree

GDB = ROOT / "data" / "full_ID_HBC.gdb"
OUT = ROOT / "results" / "stree"

LAYERS = {
    "parcel": "full_parcels_HBC",
    "road": "full_roads_hbc",
}


def run_layer(name: str, layer: str) -> None:
    out_dir = OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)

    gdf = pyogrio.read_dataframe(GDB, layer=layer, columns=[])
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty]
    bounds = gdf.geometry.bounds.to_numpy()
    items = [Item(Envelope(*b), i) for i, b in enumerate(bounds)]

    t0 = time.perf_counter()
    tree = STRtree(items, node_capacity=10)
    build_time = time.perf_counter() - t0

    regions = list(tree.regions())
    levels: dict[int, list] = {}
    for r in regions:
        levels.setdefault(r.level, []).append(r)

    # --- data output: thống kê build + danh sách envelope theo level
    stats = {
        "layer": layer,
        "n_items": len(items),
        "build_time_sec": build_time,
        "height": max(levels) + 1 if levels else 0,
        "nodes_per_level": {lvl: len(rs) for lvl, rs in sorted(levels.items())},
    }
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))

    with (out_dir / "regions.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["level", "minx", "miny", "maxx", "maxy"])
        for r in regions:
            w.writerow([r.level, r.envelope.minx, r.envelope.miny, r.envelope.maxx, r.envelope.maxy])

    # --- Tạo hình 
    tops = sorted(levels)
    fig, axes = plt.subplots(1, len(tops), figsize=(4.5 * len(tops), 5), dpi=110)
    if len(tops) == 1:
        axes = [axes]
    for ax, lvl in zip(axes, tops):
        gdf.plot(ax=ax, color="#dddddd", edgecolor="none")
        for r in levels[lvl]:
            e = r.envelope
            ax.add_patch(Rectangle((e.minx, e.miny), e.width, e.height,
                                    fill=False, edgecolor="crimson",
                                    linewidth=0.6 if lvl < 3 else 1.5))
        ax.set_title(f"Tầng {lvl}: {len(levels[lvl])} node")
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out_dir / "levels.png")
    plt.close(fig)

    print(f"[{name}] {len(items)} item, build={build_time:.3f}s, height={stats['height']} "
          f"-> {out_dir}")


def main():
    for name, layer in LAYERS.items():
        run_layer(name, layer)


if __name__ == "__main__":
    main()
