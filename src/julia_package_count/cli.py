from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from julia_package_count.chart import write_chart
from julia_package_count.registry import (
    REGISTRY_URL,
    build_snapshots,
    ensure_registry,
    growth_by_year,
    write_growth_csv,
    write_snapshot_csv,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    current_year = datetime.now(timezone.utc).year
    parser = argparse.ArgumentParser(
        description="Count Julia General registry packages over time, excluding JLL packages."
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path(".cache/General"),
        help="Path where JuliaRegistries/General is cloned or already exists.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for CSV and chart outputs.",
    )
    parser.add_argument("--remote-url", default=REGISTRY_URL, help="Registry git remote URL.")
    parser.add_argument("--branch", default="master", help="Registry branch to inspect.")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2018,
        help="First Jan 1 snapshot year to include.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=current_year,
        help="Last Jan 1 snapshot year to include.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Use an existing registry checkout without fetching updates.",
    )
    parser.add_argument(
        "--no-initial",
        action="store_true",
        help="Do not include the first non-empty General commit before Jan 1 snapshots.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ref_name = ensure_registry(
        registry_dir=args.registry_dir,
        remote_url=args.remote_url,
        branch=args.branch,
        fetch=not args.no_fetch,
    )
    snapshots = build_snapshots(
        repo_dir=args.registry_dir,
        ref_name=ref_name,
        start_year=args.start_year,
        end_year=args.end_year,
        include_initial=not args.no_initial,
    )
    growth = growth_by_year(snapshots)

    first_year = snapshots[0].date[:4]
    snapshot_csv = args.output_dir / f"julia_general_nonjll_packages_{first_year}_{args.end_year}.csv"
    growth_csv = (
        args.output_dir
        / f"julia_general_nonjll_package_growth_by_year_{first_year}_{args.end_year - 1}.csv"
    )
    chart_stem = args.output_dir / f"julia_general_nonjll_packages_{first_year}_{args.end_year}"

    write_snapshot_csv(snapshots, snapshot_csv)
    write_growth_csv(growth, growth_csv)
    chart_paths = write_chart(snapshots, growth, chart_stem)

    for path in [snapshot_csv, growth_csv, *chart_paths]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
