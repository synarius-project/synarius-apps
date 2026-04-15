"""Tests for synarius_parawiz.app.parameter_compare_logic (pure Python, no Qt)."""

from __future__ import annotations

from uuid import uuid4

from synarius_parawiz.app.parameter_compare_logic import (
    compute_row_compare_snapshot,
    neutral_row_compare_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FP:
    """Minimal fake fingerprint with a value and a meta attribute."""

    def __init__(self, value: str, meta: str) -> None:
        self.value = value
        self.meta = meta


def _va_key(fp: _FP) -> str:
    return fp.value


def _meta_key(fp: _FP) -> str:
    return fp.meta


# ---------------------------------------------------------------------------
# neutral_row_compare_snapshot
# ---------------------------------------------------------------------------

class TestNeutralSnapshot:
    def test_is_stable_singleton(self) -> None:
        assert neutral_row_compare_snapshot() is neutral_row_compare_snapshot()

    def test_all_fields_are_neutral(self) -> None:
        s = neutral_row_compare_snapshot()
        assert s.present_dataset_count == 0
        assert s.dataset_count == 0
        assert not s.comparable
        assert not s.has_missing_dataset
        assert not s.values_differ
        assert not s.meta_differ
        assert not s.meta_differ_only
        assert not s.has_any_difference
        assert not s.row_bold
        assert not s.star_suffix
        assert s.value_cluster_by_dataset_col == {}
        assert s.meta_cluster_by_dataset_col == {}


# ---------------------------------------------------------------------------
# compute_row_compare_snapshot — fewer than 2 datasets
# ---------------------------------------------------------------------------

class TestFewerThanTwoDatasets:
    def test_empty_datasets_returns_not_comparable(self) -> None:
        result = compute_row_compare_snapshot(
            by_ds={},
            datasets=[],
            fp_by_id={},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert not result.comparable
        assert result.dataset_count == 0
        assert result.present_dataset_count == 0

    def test_single_dataset_present_not_comparable(self) -> None:
        ds_id = uuid4()
        fp_id = uuid4()
        fp = _FP("1.0", "unit")
        result = compute_row_compare_snapshot(
            by_ds={ds_id: ("name", "1.0", fp_id)},
            datasets=[("DS1", ds_id)],
            fp_by_id={fp_id: fp},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert not result.comparable
        assert result.dataset_count == 1
        assert result.present_dataset_count == 1
        assert not result.has_missing_dataset

    def test_single_dataset_absent_not_comparable(self) -> None:
        ds_id = uuid4()
        result = compute_row_compare_snapshot(
            by_ds={},
            datasets=[("DS1", ds_id)],
            fp_by_id={},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert not result.comparable
        assert result.present_dataset_count == 0


# ---------------------------------------------------------------------------
# compute_row_compare_snapshot — two datasets, both present
# ---------------------------------------------------------------------------

class TestTwoDatasetsIdentical:
    def test_identical_values_and_meta(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        fp1 = _FP("1.0", "m")
        fp2 = _FP("1.0", "m")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id), ds2: ("n", "1.0", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert not result.values_differ
        assert not result.meta_differ
        assert not result.meta_differ_only
        assert not result.has_any_difference
        assert not result.row_bold
        assert not result.star_suffix
        assert result.present_dataset_count == 2
        assert result.dataset_count == 2
        assert not result.has_missing_dataset
        assert result.value_cluster_by_dataset_col[0] == result.value_cluster_by_dataset_col[1]
        assert result.meta_cluster_by_dataset_col[0] == result.meta_cluster_by_dataset_col[1]


class TestTwoDatasetsValuesDiffer:
    def test_different_values_same_meta(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        fp1 = _FP("1.0", "m")
        fp2 = _FP("2.0", "m")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id), ds2: ("n", "2.0", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert result.values_differ
        assert not result.meta_differ
        assert not result.meta_differ_only
        assert result.has_any_difference
        assert result.row_bold
        assert not result.star_suffix
        assert result.value_cluster_by_dataset_col[0] != result.value_cluster_by_dataset_col[1]

    def test_different_values_and_meta(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        fp1 = _FP("1.0", "unit_a")
        fp2 = _FP("2.0", "unit_b")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id), ds2: ("n", "2.0", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.values_differ
        assert result.meta_differ
        assert not result.meta_differ_only  # values also differ


class TestTwoDatasetsMetaDifferOnly:
    def test_same_values_different_meta(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        fp1 = _FP("1.0", "unit_a")
        fp2 = _FP("1.0", "unit_b")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id), ds2: ("n", "1.0", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert not result.values_differ
        assert result.meta_differ
        assert result.meta_differ_only
        assert result.has_any_difference
        assert not result.row_bold
        assert result.star_suffix
        assert result.meta_cluster_by_dataset_col[0] != result.meta_cluster_by_dataset_col[1]


class TestTwoDatasetsOneMissing:
    def test_one_absent_in_by_ds(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id = uuid4()
        fp1 = _FP("1.0", "m")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={fp1_id: fp1},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert not result.comparable
        assert result.has_missing_dataset
        assert result.present_dataset_count == 1
        assert result.dataset_count == 2
        assert result.has_any_difference

    def test_fp_not_in_fp_by_id(self) -> None:
        ds1, ds2 = uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "v", fp1_id), ds2: ("n", "v", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2)],
            fp_by_id={},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert not result.comparable
        assert result.present_dataset_count == 0


# ---------------------------------------------------------------------------
# compute_row_compare_snapshot — three or more datasets
# ---------------------------------------------------------------------------

class TestThreeDatasets:
    def test_three_two_clusters(self) -> None:
        ds1, ds2, ds3 = uuid4(), uuid4(), uuid4()
        fp1_id, fp2_id, fp3_id = uuid4(), uuid4(), uuid4()
        fp1 = _FP("1.0", "m")
        fp2 = _FP("2.0", "m")
        fp3 = _FP("1.0", "m")  # same cluster as fp1
        result = compute_row_compare_snapshot(
            by_ds={
                ds1: ("n", "1.0", fp1_id),
                ds2: ("n", "2.0", fp2_id),
                ds3: ("n", "1.0", fp3_id),
            },
            datasets=[("DS1", ds1), ("DS2", ds2), ("DS3", ds3)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2, fp3_id: fp3},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert result.values_differ
        c = result.value_cluster_by_dataset_col
        assert c[0] == c[2]   # DS1 and DS3 are identical
        assert c[0] != c[1]   # DS2 differs

    def test_three_all_same(self) -> None:
        ds1, ds2, ds3 = uuid4(), uuid4(), uuid4()
        fp1_id, fp2_id, fp3_id = uuid4(), uuid4(), uuid4()
        fp1 = _FP("1.0", "m")
        fp2 = _FP("1.0", "m")
        fp3 = _FP("1.0", "m")
        result = compute_row_compare_snapshot(
            by_ds={
                ds1: ("n", "1.0", fp1_id),
                ds2: ("n", "1.0", fp2_id),
                ds3: ("n", "1.0", fp3_id),
            },
            datasets=[("DS1", ds1), ("DS2", ds2), ("DS3", ds3)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2, fp3_id: fp3},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert not result.values_differ
        assert not result.has_any_difference

    def test_three_one_missing_still_comparable(self) -> None:
        ds1, ds2, ds3 = uuid4(), uuid4(), uuid4()
        fp1_id, fp2_id = uuid4(), uuid4()
        fp1 = _FP("1.0", "m")
        fp2 = _FP("2.0", "m")
        result = compute_row_compare_snapshot(
            by_ds={ds1: ("n", "1.0", fp1_id), ds2: ("n", "2.0", fp2_id)},
            datasets=[("DS1", ds1), ("DS2", ds2), ("DS3", ds3)],
            fp_by_id={fp1_id: fp1, fp2_id: fp2},
            va_key_fn=_va_key,
            meta_key_fn=_meta_key,
        )
        assert result.comparable
        assert result.has_missing_dataset
        assert result.present_dataset_count == 2
        assert result.dataset_count == 3
