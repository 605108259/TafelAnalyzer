# tests/test_cache_import.py
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.serialization import fit_from_dict, prepared_to_dict, prepared_from_dict
from core.types import ComparisonItem, PreparedSeries, SegmentInfo
from core.cache import (
    build_v3_blobs,
    build_v3_comparison,
    build_v3_file_ui,
    build_v3_manifest,
    build_v3_result_index,
    cache_key_to_json,
    load_v3_project_dir,
    load_v3_project_zip,
    make_result_cache_key,
    write_v3_project_dir,
    write_v3_project_zip,
)


def _make_prepared() -> PreparedSeries:
    seg = SegmentInfo(index=0, start=0, end=10)
    return PreparedSeries(
        raw_e=np.linspace(0, 1, 10),
        raw_j=np.logspace(-6, -3, 10),
        e=np.linspace(0, 1, 10),
        j=np.logspace(-6, -3, 10),
        eta=np.linspace(0, 1, 10),
        e_label="[V]",
        j_label="[Igs/area]",
        tafel_y_label="过电位（V）",
        potential_channel="V",
        current_channel="Igs/area",
        potential_formula="[V]",
        current_formula="[Igs/area]",
        e_eq=0.0,
        segment=seg,
    )


def test_import_cache_restores_prepared_by_segment():
    """缓存导入应完整恢复 prepared_by_segment 字段。"""
    prepared = _make_prepared()
    serialized = {"prepared_by_segment": {"0": prepared_to_dict(prepared)}}
    restored = {
        int(k): prepared_from_dict(v)
        for k, v in serialized["prepared_by_segment"].items()
    }
    assert 0 in restored
    assert np.allclose(restored[0].e, prepared.e)


def test_prepared_from_dict_recomputes_signed_eta_for_legacy_abs_cache():
    prepared = _make_prepared()
    data = prepared_to_dict(prepared)
    data["e"] = [-0.2, 0.0, 0.3]
    data["eta"] = [0.3, 0.1, 0.2]
    data["e_eq"] = 0.1

    restored = prepared_from_dict(data)

    assert np.allclose(restored.eta, [0.3, 0.1, -0.2])


def test_fit_from_dict_filters_extreme_tafel_points():
    restored = fit_from_dict(
        {
            "slope_v_per_dec": 1.0,
            "intercept_v": 0.0,
            "r2": 0.99,
            "x_log10_j": [0.0, 1.0, 10.0],
            "y_e": [0.0, 0.1, 1.3068769334e10],
            "selected_mask": [True, True, True],
            "source_indices": [0, 1, 2],
            "mode": "auto",
        }
    )

    assert np.allclose(restored.x_log10_j, [0.0, 1.0])
    assert np.allclose(restored.y_e, [0.0, 0.1])
    assert np.array_equal(restored.selected_mask, [True, True])
    assert np.array_equal(restored.source_indices, [0, 1])


def test_import_cache_restores_fit_error_by_segment():
    """缓存导入应完整恢复 fit_error_by_segment 字段。"""
    raw_errors = {"0": "数据点不足", "1": "R² 不达标"}
    restored = {int(k): v for k, v in raw_errors.items()}
    assert restored[0] == "数据点不足"
    assert restored[1] == "R² 不达标"


def test_v3_cache_roundtrip_restores_result_key_and_comparison_refs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_path = root / "sample.cor"
        data_path.write_text("same data", encoding="utf-8")
        prepared = _make_prepared()
        cache_key = make_result_cache_key(
            tdms_path=data_path,
            potential_formula="[V]",
            current_formula="[Igs/area]",
            e_eq=0.0,
            selected_segment_indices=(0,),
            min_window=12,
            max_window=15,
            eta_range=None,
            logj_range=None,
            min_r2=0.95,
            fit_priority="slope_low",
        )
        app = SimpleNamespace(
            fig=SimpleNamespace(axes=[]),
            state=SimpleNamespace(files=SimpleNamespace(current_path=data_path)),
            _app_state={
                "current_project_id": "project-1",
                "current_project_title": "project",
                "selected_paths": [data_path],
                "tdms_path": data_path,
                "active_chart_mode": None,
                "single_plot_view_state": None,
                "compare_plot_view_state": None,
                "file_ui_cache": {
                    str(data_path): {
                        "potential_formula": "[V]",
                        "current_formula": "[Igs/area]",
                    }
                },
                "current_result_keys": {str(data_path): cache_key},
                "result_cache": {
                    cache_key: {
                        "prepared": prepared,
                        "fit": None,
                        "prepared_by_segment": {0: prepared},
                        "fit_by_segment": {},
                        "fit_error_by_segment": {},
                        "manual_fit_regions": {
                            0: {"x_min": 0, "x_max": 1, "y_min": 0, "y_max": 1}
                        },
                        "selected_segment_indices": [0],
                        "active_segment_index": 0,
                        "view_state": None,
                    }
                },
                "comparison_items": [
                    ComparisonItem(
                        item_id="item-1",
                        file_path=data_path,
                        file_name="sample",
                        segment_index=0,
                        prepared=prepared,
                        fit=None,
                        label="sample",
                        color="#2563eb",
                    )
                ],
            },
        )

        project_dir = root / "history" / "project"
        write_v3_project_dir(
            project_dir,
            build_v3_manifest(app),
            build_v3_file_ui(app),
            build_v3_result_index(app),
            build_v3_comparison(app),
            *build_v3_blobs(app),
        )
        payload = load_v3_project_dir(project_dir)

        assert payload["current_result_keys"][str(data_path)] == cache_key_to_json(cache_key)
        assert payload["result_cache"][0]["prepared_by_segment"]["0"] is not None
        assert payload["comparison_items"][0]["prepared"] is not None


def test_v3_cache_zip_roundtrip_restores_result_key_and_comparison_refs(tmp_path):
    data_path = tmp_path / "sample.cor"
    data_path.write_text("same data", encoding="utf-8")
    prepared = _make_prepared()
    cache_key = make_result_cache_key(
        tdms_path=data_path,
        potential_formula="[V]",
        current_formula="[Igs/area]",
        e_eq=0.0,
        selected_segment_indices=(0,),
        min_window=12,
        max_window=15,
        eta_range=None,
        logj_range=None,
        min_r2=0.95,
        fit_priority="slope_low",
    )
    app = SimpleNamespace(
        fig=SimpleNamespace(axes=[]),
        state=SimpleNamespace(files=SimpleNamespace(current_path=data_path)),
        _app_state={
            "current_project_id": "project-1",
            "current_project_title": "project",
            "selected_paths": [data_path],
            "tdms_path": data_path,
            "active_chart_mode": None,
            "single_plot_view_state": None,
            "compare_plot_view_state": None,
            "file_ui_cache": {str(data_path): {"potential_formula": "[V]"}},
            "current_result_keys": {str(data_path): cache_key},
            "result_cache": {
                cache_key: {
                    "prepared": prepared,
                    "fit": None,
                    "prepared_by_segment": {0: prepared},
                    "fit_by_segment": {},
                    "fit_error_by_segment": {},
                    "manual_fit_regions": {},
                    "selected_segment_indices": [0],
                    "active_segment_index": 0,
                    "view_state": None,
                }
            },
            "comparison_items": [
                ComparisonItem(
                    item_id="item-1",
                    file_path=data_path,
                    file_name="sample",
                    segment_index=0,
                    prepared=prepared,
                    fit=None,
                    label="sample",
                    color="#2563eb",
                )
            ],
        },
    )
    zip_path = tmp_path / "project_cache.zip"

    write_v3_project_zip(
        zip_path,
        build_v3_manifest(app),
        build_v3_file_ui(app),
        build_v3_result_index(app),
        build_v3_comparison(app),
        *build_v3_blobs(app),
    )
    payload = load_v3_project_zip(zip_path)

    assert payload["current_result_keys"][str(data_path)] == cache_key_to_json(cache_key)
    assert payload["result_cache"][0]["prepared_by_segment"]["0"] is not None
    assert payload["comparison_items"][0]["prepared"] is not None


def test_v3_cache_load_skips_result_entries_with_missing_prepared_blob(tmp_path):
    project_dir = tmp_path / "broken-project"
    project_dir.mkdir()
    (project_dir / "prepared").mkdir()
    (project_dir / "fits").mkdir()
    (project_dir / "manifest.json").write_text(
        '{"cache_format_version":3,"selected_paths":[],"current_path":null,"chart_view_state":{}}',
        encoding="utf-8",
    )
    (project_dir / "file_ui.json").write_text("{}", encoding="utf-8")
    (project_dir / "comparison.json").write_text('{"items":[]}', encoding="utf-8")
    (project_dir / "result_index.json").write_text(
        json.dumps(
            {
                "[broken]": {
                    "key": ["broken"],
                    "active_segment_index": 0,
                    "prepared_refs": {"0": "missing_s0"},
                    "fit_refs": {},
                }
            }
        ),
        encoding="utf-8",
    )

    payload = load_v3_project_dir(project_dir)

    assert payload["result_cache"] == []
