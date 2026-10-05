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
- `output/julia_general_nonjll_released_last_12m.csv`
- `output/julia_general_nonjll_released_last_12m.png`
- `output/julia_general_nonjll_released_last_12m.pdf`
- `output/julia_general_nonjll_released_last_12m.svg`

## Counting Rules

- Count root registry entries matching `[A-Z0-9]/PackageName/[Pp]ackage.toml`.
- Exclude historical root-level JLL packages where `PackageName` ends in `_jll`.
- Exclude newer JLL packages under `jll/[A-Z0-9]/PackageName/Package.toml`.
- Include the first non-empty General commit, `2017-08-29`, as `2017*`.
- Treat later points as Jan 1 snapshots.

The General registry begins in 2017. Earlier Julia package history lived in `JuliaLang/METADATA.jl` and is not analyzed by this tool.

### Rolling release counts

The monthly series answers a different question: how many packages were updated in the
previous 12 months, as a function of time. It reads `Versions.toml` patches from the registry
history and counts a package when a version entry was added in the trailing 365 days, so a
package with several releases inside the window still counts once. `registered` is the non-JLL
package count at that month start, so the ratio approximates the share of registered packages
that were released in the past year; a package removed from the registry during the window is
still counted as released.

Counting added version entries instead of `Versions.toml` changes matters: registry-wide
commits such as `remove packages and versions that do not support Julia 1.0 (#4169)`, which
rewrote 2,031 `Versions.toml` files in 2019-10, would otherwise all look like releases.

Because of this the registry clone is not filtered (`--filter=blob:none` is not used): reading
patches from a partial clone fetches blobs one at a time over the network. The series starts at
the first month start with a full 12-month window inside the registry history (2018-09) and
ends at the start of the month of the registry head, so its final window is slightly
incomplete. It is independent of `--start-year`, `--end-year` and `--no-initial`.

## Development

```sh
uv run --group dev pytest -q
```
