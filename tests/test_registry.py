import os
import subprocess
from datetime import datetime, timezone

import pytest

from julia_package_count.registry import (
    Snapshot,
    classify_package_toml,
    count_package_paths,
    ensure_registry,
    growth_by_year,
    month_starts,
    monthly_rolling_counts,
    package_name_from_versions_toml,
    release_events,
    rolling_counts,
)


def test_classifies_old_and_new_registry_package_paths():
    assert classify_package_toml("A/Example/package.toml") == "non_jll"
    assert classify_package_toml("A/Example/Package.toml") == "non_jll"
    assert classify_package_toml("A/Example_jll/Package.toml") == "jll"
    assert classify_package_toml("jll/A/Example_jll/Package.toml") == "jll"


def test_ignores_non_package_registry_paths():
    assert classify_package_toml("A/Example/Versions.toml") is None
    assert classify_package_toml("docs/A/Example/Package.toml") is None
    assert classify_package_toml("jll/A/Example_jll/Versions.toml") is None
    assert classify_package_toml("a/Example/Package.toml") is None


def test_counts_non_jll_and_jll_paths():
    counts = count_package_paths(
        [
            "A/Alpha/package.toml",
            "B/Beta/Package.toml",
            "C/Codec_jll/Package.toml",
            "jll/D/Delta_jll/Package.toml",
            "A/Alpha/Versions.toml",
        ]
    )

    assert counts.non_jll == 2
    assert counts.jll == 2
    assert counts.total == 4


def test_growth_by_year_uses_intervals_not_destination_snapshot_labels():
    snapshots = [
        Snapshot(label="2017*", date="2017-08-29", non_jll=1541, jll=0, ref="a", note="initial"),
        Snapshot(label="2018", date="2018-01-01", non_jll=1691, jll=0, ref="b", note="snapshot"),
        Snapshot(label="2019", date="2019-01-01", non_jll=2424, jll=0, ref="c", note="snapshot"),
        Snapshot(label="2020", date="2020-01-01", non_jll=2671, jll=209, ref="d", note="snapshot"),
    ]

    assert growth_by_year(snapshots) == [
        ("2017 partial", 150),
        ("2018", 733),
        ("2019", 247),
    ]


def test_package_name_from_versions_toml_excludes_jll_paths():
    assert package_name_from_versions_toml("A/Alpha/Versions.toml") == "Alpha"
    assert package_name_from_versions_toml("A/Alpha_jll/Versions.toml") is None
    assert package_name_from_versions_toml("jll/A/Alpha_jll/Versions.toml") is None
    assert package_name_from_versions_toml("A/Alpha/Package.toml") is None
    assert package_name_from_versions_toml("a/Alpha/Versions.toml") is None


def test_rolling_counts_count_each_package_once_per_window():
    months = month_starts(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 12, 1, tzinfo=timezone.utc))
    events = {
        "Alpha": [
            datetime(2024, 3, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            datetime(2024, 5, 1, tzinfo=timezone.utc),
        ]
    }

    counts = dict(zip(months, rolling_counts(events, months)))

    assert counts[datetime(2024, 2, 1, tzinfo=timezone.utc)] == 0
    assert counts[datetime(2024, 3, 1, tzinfo=timezone.utc)] == 1
    assert counts[datetime(2024, 12, 1, tzinfo=timezone.utc)] == 1


def test_rolling_counts_use_earlier_releases_for_past_months():
    # Delta released again after 2025-01-01; the 2024-06-01 release must still count for
    # that month instead of the package being dropped from the window.
    months = month_starts(datetime(2024, 6, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
    events = {
        "Delta": [
            datetime(2024, 6, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        ]
    }

    counts = dict(zip(months, rolling_counts(events, months)))

    assert counts[datetime(2025, 1, 1, tzinfo=timezone.utc)] == 1
    assert counts[datetime(2025, 5, 1, tzinfo=timezone.utc)] == 1
    assert counts[datetime(2025, 6, 1, tzinfo=timezone.utc)] == 0
    assert counts[datetime(2026, 5, 1, tzinfo=timezone.utc)] == 0
    assert counts[datetime(2026, 6, 1, tzinfo=timezone.utc)] == 1


def test_release_events_require_an_added_version(tmp_path):
    repo = tmp_path / "registry"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def write(path: str, text: str) -> None:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(date: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", date],
            cwd=repo,
            check=True,
            env={**env, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
        )

    write("A/Alpha/Versions.toml", '["0.1.0"]\n')
    write("A/Alpha_jll/Versions.toml", '["0.1.0"]\n')
    write("jll/B/Beta_jll/Versions.toml", '["0.1.0"]\n')
    commit("2024-03-01T00:00:00+00:00")
    write("A/Alpha/Versions.toml", '["0.1.0"]\n["0.2.0"]\n')
    commit("2024-03-02T00:00:00+00:00")
    # a registry-wide rewrite that prunes a version is not a release
    write("A/Alpha/Versions.toml", '["0.2.0"]\n')
    write("A/Alpha_jll/Versions.toml", '["0.2.0"]\n')
    commit("2024-03-03T00:00:00+00:00")
    subprocess.run(["git", "branch", "-M", "master"], cwd=repo, check=True)

    events = release_events(repo, "master", since="2024-01-01")

    assert {name: [date.date().isoformat() for date in dates] for name, dates in events.items()} == {
        "Alpha": ["2024-03-01", "2024-03-02"],
    }



def _init_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def test_ensure_registry_accepts_an_unfiltered_existing_clone(tmp_path):
    repo = _init_repo(tmp_path / "General")

    assert ensure_registry(repo, fetch=False) == "origin/master"


def test_ensure_registry_rejects_a_partial_clone(tmp_path):
    repo = _init_repo(tmp_path / "General")
    subprocess.run(
        ["git", "config", "remote.origin.partialclonefilter", "blob:none"],
        cwd=repo,
        check=True,
    )

    with pytest.raises(RuntimeError, match="partial clone"):
        ensure_registry(repo, fetch=False)


def test_monthly_rolling_counts_start_at_the_first_full_window(tmp_path):
    repo = _init_repo(tmp_path / "General")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def commit(date: str, message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", message],
            cwd=repo,
            check=True,
            env={**env, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
        )

    (repo / "A" / "Alpha").mkdir(parents=True)
    (repo / "A" / "Alpha" / "Package.toml").write_text('name = "Alpha"\n')
    (repo / "A" / "Alpha" / "Versions.toml").write_text('["0.1.0"]\n')
    commit("2020-01-01T12:00:00+00:00", "first package")
    (repo / "A" / "Alpha" / "Versions.toml").write_text('["0.1.0"]\n["0.2.0"]\n')
    commit("2020-06-01T12:00:00+00:00", "second version")
    subprocess.run(["git", "branch", "-M", "master"], cwd=repo, check=True)

    rows = monthly_rolling_counts(repo, "master", end=datetime(2021, 3, 1, tzinfo=timezone.utc))

    # 2020-01-01 + 365 days is 2020-12-31, so the first month with a full window is 2021-01,
    # and the 2020-06-01 release is the one inside that window.
    assert [row.month for row in rows] == ["2021-01-01", "2021-02-01", "2021-03-01"]
    assert [row.released_last_12m for row in rows] == [1, 1, 1]
    assert [row.registered for row in rows] == [1, 1, 1]
