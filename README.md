# julia-package-count

Count packages in the Julia General registry over time while excluding JLL packages, then generate CSV and chart artifacts.

The checked-in `output/` directory includes the generated CSV, PNG, PDF, and SVG for the current General-registry range used here.

## Usage

```sh
uv run julia-package-count
```

By default this clones or updates `JuliaRegistries/General` into `.cache/General` and writes outputs under `output/`.

To reproduce the committed 2017-2026 artifacts exactly:

```sh
uv run julia-package-count --end-year 2026
```

If you already have a local General checkout:

```sh
uv run julia-package-count --registry-dir /path/to/General --no-fetch --output-dir output --end-year 2026
```

## Outputs

- `output/julia_general_nonjll_packages_2017_2026.csv`
- `output/julia_general_nonjll_package_growth_by_year_2017_2025.csv`
- `output/julia_general_nonjll_packages_2017_2026.png`
- `output/julia_general_nonjll_packages_2017_2026.pdf`
- `output/julia_general_nonjll_packages_2017_2026.svg`

## Counting Rules

- Count root registry entries matching `[A-Z0-9]/PackageName/[Pp]ackage.toml`.
- Exclude historical root-level JLL packages where `PackageName` ends in `_jll`.
- Exclude newer JLL packages under `jll/[A-Z0-9]/PackageName/Package.toml`.
- Include the first non-empty General commit, `2017-08-29`, as `2017*`.
- Treat later points as Jan 1 snapshots.

The General registry begins in 2017. Earlier Julia package history lived in `JuliaLang/METADATA.jl` and is not analyzed by this tool.

## Development

```sh
uv run --group dev pytest -q
```
