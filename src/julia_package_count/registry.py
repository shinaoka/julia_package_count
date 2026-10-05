from __future__ import annotations

import csv
import re
import subprocess
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import accumulate
from pathlib import Path
from typing import Iterable

REGISTRY_URL = "https://github.com/JuliaRegistries/General.git"
ROLLING_WINDOW_DAYS = 365
ROOT_LETTER_RE = re.compile(r"^[A-Z0-9]$")
VERSION_HEADER_RE = re.compile(r'^\+\["[^"]+"\]\s*$')


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


@dataclass(frozen=True)
class RollingPackageCount:
    month: str
    released_last_12m: int
    registered: int


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
    """Clone or update General and return the ref name to query.

    The clone is not filtered: release detection reads Versions.toml patches, which a
    blobless partial clone can only fetch blob by blob over the network.
    """
    registry_dir = registry_dir.resolve()
    ref_name = f"origin/{branch}"

    if (registry_dir / ".git").exists():
        partial = subprocess.run(
            ["git", "config", "--get", "remote.origin.partialclonefilter"],
            cwd=registry_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if partial:
            raise RuntimeError(
                f"{registry_dir} is a partial clone ({partial}); delete it and re-run so a "
                "full clone is made, otherwise reading Versions.toml patches is very slow."
            )
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


def package_name_from_versions_toml(path: str) -> str | None:
    """Registry package name for a Versions.toml path, or None for JLL/irrelevant paths."""
    parts = path.strip().split("/")

    if len(parts) == 3 and ROOT_LETTER_RE.fullmatch(parts[0]) and parts[2] == "Versions.toml":
        return None if parts[1].endswith("_jll") else parts[1]

    return None


def release_events(repo_dir: Path, ref: str, since: str) -> dict[str, list[datetime]]:
    """Non-JLL package name -> UTC dates of a version added to Versions.toml, oldest first.

    Only added version entries count, so registry-wide commits that rewrite or prune
    Versions.toml files (for example the 2019-10 Julia 1.0 cleanup) are not releases.
    """
    log = git_output(
        repo_dir,
        "log",
        "-p",
        "--unified=0",
        "--format=%x00%cI",
        f"--since={since}",
        ref,
        "--",
        "*/Versions.toml",
    )

    events: dict[str, list[datetime]] = {}
    for chunk in log.split("\0")[1:]:
        lines = chunk.splitlines()
        if not lines:
            continue
        committed_at = datetime.fromisoformat(lines[0].strip()).astimezone(timezone.utc)
        released: set[str] = set()
        path: str | None = None
        for line in lines[1:]:
            if line.startswith("+++ "):
                path = line[4:].removeprefix("b/").strip()
            elif path is not None and VERSION_HEADER_RE.match(line):
                name = package_name_from_versions_toml(path)
                if name is not None:
                    released.add(name)
        for name in released:
            events.setdefault(name, []).append(committed_at)

    for dates in events.values():
        dates.sort()
    return events


def month_starts(start: datetime, end: datetime) -> list[datetime]:
    month = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months: list[datetime] = []
    while month <= end:
        months.append(month)
        month = (month.replace(day=28) + timedelta(days=5)).replace(day=1)
    return months


def rolling_counts(
    events: dict[str, list[datetime]],
    months: list[datetime],
) -> list[int]:
    """Packages with any release in (month - ROLLING_WINDOW_DAYS, month], once per package.

    A package with several releases inside the window must still count once, so its release
    history is reduced to the intervals [release, min(next release, release + window)).
    """
    window = timedelta(days=ROLLING_WINDOW_DAYS)
    delta = [0] * (len(months) + 1)

    for releases in events.values():
        for index, release in enumerate(releases):
            end = release + window
            if index + 1 < len(releases) and releases[index + 1] < end:
                end = releases[index + 1]
            start_month = bisect_left(months, release)
            end_month = bisect_left(months, end)
            if end_month > start_month:
                delta[start_month] += 1
                delta[end_month] -= 1

    return list(accumulate(delta))[: len(months)]


def head_commit_date(repo_dir: Path, ref: str) -> datetime:
    return datetime.fromisoformat(
        git_output(repo_dir, "log", "-1", "--format=%cI", ref).strip()
    ).astimezone(timezone.utc)


def monthly_rolling_counts(
    repo_dir: Path,
    ref_name: str,
    end: datetime,
) -> list[RollingPackageCount]:
    """Monthly count of packages released in the trailing window, plus registry size.

    The series starts at the first month start that has a full window inside the registry
    history, so the window never reaches back before the registry exists.
    """
    history_start = datetime.fromisoformat(
        first_non_empty_snapshot(repo_dir, ref_name).date
    ).replace(tzinfo=timezone.utc)
    full_window_start = history_start + timedelta(days=ROLLING_WINDOW_DAYS)
    months = [month for month in month_starts(history_start, end) if month >= full_window_start]

    events = release_events(repo_dir, ref_name, since=history_start.date().isoformat())
    released = rolling_counts(events, months)

    rows: list[RollingPackageCount] = []
    for month, count in zip(months, released):
        date = month.date().isoformat()
        ref = snapshot_before(repo_dir, ref_name, f"{date}T00:00:00Z")
        registered = count_ref(repo_dir, ref).non_jll if ref is not None else 0
        rows.append(
            RollingPackageCount(month=date, released_last_12m=count, registered=registered)
        )
    return rows


def write_rolling_csv(rows: list[RollingPackageCount], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["month", "released_last_12m", "registered"])
        for row in rows:
            writer.writerow([row.month, row.released_last_12m, row.registered])
