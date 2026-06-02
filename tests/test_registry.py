from julia_package_count.registry import (
    Snapshot,
    classify_package_toml,
    count_package_paths,
    growth_by_year,
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
