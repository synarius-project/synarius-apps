"""Shared row-compare logic for global filters and local styling."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RowCompareSnapshot:
    """Pure comparison outcome for one parameter row across data sets."""

    present_dataset_count: int
    dataset_count: int
    comparable: bool
    has_missing_dataset: bool
    values_differ: bool
    meta_differ: bool
    meta_differ_only: bool
    has_any_difference: bool
    row_bold: bool
    star_suffix: bool
    value_cluster_by_dataset_col: dict[int, int]
    meta_cluster_by_dataset_col: dict[int, int]


_NEUTRAL_SNAPSHOT = RowCompareSnapshot(
    present_dataset_count=0,
    dataset_count=0,
    comparable=False,
    has_missing_dataset=False,
    values_differ=False,
    meta_differ=False,
    meta_differ_only=False,
    has_any_difference=False,
    row_bold=False,
    star_suffix=False,
    value_cluster_by_dataset_col={},
    meta_cluster_by_dataset_col={},
)


def neutral_row_compare_snapshot() -> RowCompareSnapshot:
    return _NEUTRAL_SNAPSHOT


def compute_row_compare_snapshot(
    *,
    by_ds: dict[UUID, tuple[str, str, UUID]],
    datasets: list[tuple[str, UUID]],
    fp_by_id: dict[UUID, object],
    va_key_fn,
    meta_key_fn,
) -> RowCompareSnapshot:
    n_ds = len(datasets)
    if n_ds < 2:
        return RowCompareSnapshot(
            present_dataset_count=sum(1 for _n, ds_id in datasets if by_ds.get(ds_id) is not None),
            dataset_count=n_ds,
            comparable=False,
            has_missing_dataset=False,
            values_differ=False,
            meta_differ=False,
            meta_differ_only=False,
            has_any_difference=False,
            row_bold=False,
            star_suffix=False,
            value_cluster_by_dataset_col={},
            meta_cluster_by_dataset_col={},
        )

    present: list[tuple[int, object]] = []
    for i, (_name, ds_id) in enumerate(datasets):
        hit = by_ds.get(ds_id)
        if hit is None:
            continue
        fp = fp_by_id.get(hit[2])
        if fp is None:
            continue
        present.append((i, fp))
    present_n = len(present)
    comparable = present_n >= 2
    has_missing_dataset = present_n < n_ds
    if not comparable:
        return RowCompareSnapshot(
            present_dataset_count=present_n,
            dataset_count=n_ds,
            comparable=False,
            has_missing_dataset=has_missing_dataset,
            values_differ=False,
            meta_differ=False,
            meta_differ_only=False,
            has_any_difference=has_missing_dataset,
            row_bold=False,
            star_suffix=False,
            value_cluster_by_dataset_col={},
            meta_cluster_by_dataset_col={},
        )

    va_vals = [va_key_fn(fp) for _i, fp in present]
    meta_vals = [meta_key_fn(fp) for _i, fp in present]
    va_unique = list(dict.fromkeys(va_vals))
    meta_unique = list(dict.fromkeys(meta_vals))
    values_differ = len(va_unique) > 1
    meta_differ = len(meta_unique) > 1
    meta_differ_only = (not values_differ) and meta_differ
    has_any_difference = has_missing_dataset or values_differ or meta_differ_only
    va_cluster = {v: idx for idx, v in enumerate(va_unique)}
    meta_cluster = {v: idx for idx, v in enumerate(meta_unique)}
    value_cluster_by_dataset_col: dict[int, int] = {}
    meta_cluster_by_dataset_col: dict[int, int] = {}
    for (col_i, _fp), va_v, meta_v in zip(present, va_vals, meta_vals, strict=True):
        value_cluster_by_dataset_col[col_i] = va_cluster[va_v]
        meta_cluster_by_dataset_col[col_i] = meta_cluster[meta_v]
    return RowCompareSnapshot(
        present_dataset_count=present_n,
        dataset_count=n_ds,
        comparable=True,
        has_missing_dataset=has_missing_dataset,
        values_differ=values_differ,
        meta_differ=meta_differ,
        meta_differ_only=meta_differ_only,
        has_any_difference=has_any_difference,
        row_bold=values_differ,
        star_suffix=meta_differ_only,
        value_cluster_by_dataset_col=value_cluster_by_dataset_col,
        meta_cluster_by_dataset_col=meta_cluster_by_dataset_col,
    )

