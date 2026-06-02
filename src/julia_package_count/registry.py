from __future__ import annotations

import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REGISTRY_URL = "https://github.com/JuliaRegistries/General.git"
ROOT_LETTER_RE = re.compile(r"^[A-Z0-9]$")


@dataclass(frozen=True)
class Counts:
    non_jll: int
    jll: int

    @property
    def total(self) -> int:
        return self.non_jll + self.jll


@dataclass(frozen=True)
class Snapshot:
    label: str
    date: str
    non_jll: int
    jll: int
    ref: str
    note: str


def classify_package_toml(path: str) -> str | None:
    """Classify a registry Package.toml path as non_jll, jll, or irrelevant."""
    parts = path.strip().split("/")

    if (
        len(parts) == 3
        and ROOT_LETTER_RE.fullmatch(parts[0])
        and parts[2] in {"Package.toml", "package.toml"}
    ):
        return "jll" if parts[1].endswith("_jll") else "non_jll"

    if (
        len(parts) == 4
        and parts[0] == "jll"
        and ROOT_LETTER_RE.fullmatch(parts[1])
        and parts[3] == "Package.toml"
    ):
        return "jll"

    return None


def count_package_paths(paths: Iterable[str]) -> Counts:
    non_jll = 0
    jll = 0

    for path in paths:
        kind = classify_package_toml(path)
        if kind == "non_jll":
            non_jll += 1
        elif kind == "jll":
            jll += 1

    return Counts(non_jll=non_jll, jll=jll)


def git_output(repo_dir: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo_dir, text=True)


def ensure_registry(
    registry_dir: Path,
    remote_url: str = REGISTRY_URL,
    branch: str = "master",
    fetch: bool = True,
) -> str:
    """Clone or update General and return the ref name to query."""
    registry_dir = registry_dir.resolve()
    ref_name = f"origin/{branch}"

    if (registry_dir / ".git").exists():
        if fetch:
            subprocess.run(
                ["git", "fetch", "--prune", "origin", branch],
                cwd=registry_dir,
                check=True,
            )
        return ref_name

    registry_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--branch",
            branch,
            remote_url,
            str(registry_dir),
        ],
        check=True,
    )
    return ref_name


def tree_paths(repo_dir: Path, ref: str) -> list[str]:
    return git_output(repo_dir, "ls-tree", "-r", "--name-only", ref).splitlines()


def count_ref(repo_dir: Path, ref: str) -> Counts:
    return count_package_paths(tree_paths(repo_dir, ref))


def first_non_empty_snapshot(repo_dir: Path, ref_name: str) -> Snapshot:
    log_lines = git_output(repo_dir, "log", "--reverse", "--format=%H%x09%cI%x09%s", ref_name)

    for line in log_lines.splitlines():
        ref, committed_at, subject = line.split("\t", 2)
        counts = count_ref(repo_dir, ref)
        if counts.total > 0:
            return Snapshot(
                label=f"{committed_at[:4]}*",
                date=committed_at[:10],
                non_jll=counts.non_jll,
                jll=counts.jll,
                ref=ref,
                note=subject,
            )

    raise RuntimeError(f"No non-empty registry snapshot found in {ref_name}")


def snapshot_before(repo_dir: Path, ref_name: str, iso8601_utc: str) -> str | None:
    ref = git_output(repo_dir, "rev-list", "-n", "1", f"--before={iso8601_utc}", ref_name).strip()
    return ref or None


def build_snapshots(
    repo_dir: Path,
    ref_name: str,
    start_year: int,
    end_year: int,
    include_initial: bool = True,
) -> list[Snapshot]:
    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")

    snapshots: list[Snapshot] = []
    if include_initial:
        snapshots.append(first_non_empty_snapshot(repo_dir, ref_name))

    for year in range(start_year, end_year + 1):
        date = f"{year}-01-01"
        ref = snapshot_before(repo_dir, ref_name, f"{date}T00:00:00Z")
        if ref is None:
            continue
        counts = count_ref(repo_dir, ref)
        snapshots.append(
            Snapshot(
                label=str(year),
                date=date,
                non_jll=counts.non_jll,
                jll=counts.jll,
                ref=ref,
                note="Jan 1 snapshot",
            )
        )

    return snapshots


def growth_by_year(snapshots: list[Snapshot]) -> list[tuple[str, int]]:
    if len(snapshots) < 2:
        return []

    growth: list[tuple[str, int]] = []
    first = snapshots[0]
    second = snapshots[1]
    first_label = f"{first.date[:4]} partial" if first.label.endswith("*") else first.label
    growth.append((first_label, second.non_jll - first.non_jll))

    for index in range(1, len(snapshots) - 1):
        current = snapshots[index]
        next_snapshot = snapshots[index + 1]
        growth.append((current.label, next_snapshot.non_jll - current.non_jll))

    return growth


def write_snapshot_csv(snapshots: list[Snapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "label",
                "date",
                "non_jll_packages",
                "delta_since_previous",
                "jll_excluded",
                "total_packages",
                "ref",
                "note",
            ],
        )
        writer.writeheader()
        previous: int | None = None
        for snapshot in snapshots:
            delta = "" if previous is None else snapshot.non_jll - previous
            writer.writerow(
                {
                    "label": snapshot.label,
                    "date": snapshot.date,
                    "non_jll_packages": snapshot.non_jll,
                    "delta_since_previous": delta,
                    "jll_excluded": snapshot.jll,
                    "total_packages": snapshot.non_jll + snapshot.jll,
                    "ref": snapshot.ref,
                    "note": snapshot.note,
                }
            )
            previous = snapshot.non_jll


def write_growth_csv(growth: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["year", "non_jll_package_increase"])
        writer.writeheader()
        for label, value in growth:
            writer.writerow({"year": label, "non_jll_package_increase": value})
