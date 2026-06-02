from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_plot_view_state_does_not_persist_legend_position() -> None:
    from matplotlib.figure import Figure
    from core.rendering import capture_plot_view_state

    fig = Figure()
    ax0 = fig.add_subplot(121)
    ax1 = fig.add_subplot(122)
    ax0.plot([0, 1], [0, 1], label="left")
    ax1.plot([0, 1], [1, 0], label="right")
    ax0.legend(loc="upper right")
    ax1.legend(loc="lower left")

    state = capture_plot_view_state(SimpleNamespace(fig=fig), fig)

    assert state is not None
    assert "legend" not in state["axes"][0]
    assert "legend" not in state["axes"][1]


def test_apply_plot_view_state_resets_legacy_legend_state_to_static_location() -> None:
    from matplotlib.figure import Figure
    from core.rendering import apply_plot_view_state

    fig = Figure()
    ax0 = fig.add_subplot(121)
    ax1 = fig.add_subplot(122)
    ax0.plot([0, 1], [0, 1], label="left")
    ax1.plot([0, 1], [1, 0], label="right")
    ax0.legend(loc="lower left")
    ax1.legend(loc="lower left")
    state = {
        "axes": [
            {"xlim": [-1, 2], "ylim": [-2, 3], "legend": {"anchor": [0.2, 0.2]}},
            {"xlim": [-1, 2], "ylim": [-2, 3], "legend": {"anchor": [0.3, 0.3]}},
        ]
    }

    apply_plot_view_state(SimpleNamespace(fig=fig), [ax0, ax1], state)

    assert ax0.get_xlim() == (-1.0, 2.0)
    assert ax1.get_ylim() == (-2.0, 3.0)
    assert ax0.get_legend()._loc == 1
    assert ax1.get_legend()._loc == 1


def test_ordered_comparison_legend_ignores_plot_draw_order() -> None:
    from matplotlib.figure import Figure
    from core.comparison import _ordered_static_legend

    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [1, 0], label="B")
    ax.plot([0, 1], [0, 1], label="A")

    legend = _ordered_static_legend(ax, ["A", "B"])

    assert [text.get_text() for text in legend.get_texts()] == ["A", "B"]


def test_comparison_legend_order_is_stable_when_highlight_changes() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from core.comparison import render_comparison
    from core.types import ComparisonItem, PreparedSeries, SegmentInfo

    def prepared(offset: float) -> PreparedSeries:
        return PreparedSeries(
            raw_e=np.array([0.0, 1.0]),
            raw_j=np.array([offset, offset + 1.0]),
            e=np.array([0.0, 1.0]),
            j=np.array([offset, offset + 1.0]),
            eta=np.array([0.0, 1.0]),
            e_label="E",
            j_label="j",
            tafel_y_label="eta",
            potential_channel="E",
            current_channel="j",
            potential_formula="[E]",
            current_formula="[j]",
            e_eq=0.0,
            segment=SegmentInfo(index=0, start=0, end=2),
        )

    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    items = [
        ComparisonItem(
            item_id="a",
            file_path=Path("a.cor"),
            file_name="a",
            segment_index=0,
            prepared=prepared(1.0),
            fit=None,
            label="A",
            color="#2563eb",
        ),
        ComparisonItem(
            item_id="b",
            file_path=Path("b.cor"),
            file_name="b",
            segment_index=0,
            prepared=prepared(2.0),
            fit=None,
            label="B",
            color="#dc2626",
        ),
    ]
    app = SimpleNamespace(
        fig=fig,
        canvas=canvas,
        _app_state={
            "comparison_items": items,
            "comparison_highlight_row": 1,
            "comparison_lsv_style": "line_marker",
            "comparison_tafel_fit_window": False,
            "active_chart_mode": "comparison",
        },
    )

    render_comparison(app)
    first_labels = [text.get_text() for text in fig.axes[0].get_legend().get_texts()]
    app._app_state["comparison_highlight_row"] = 0
    render_comparison(app)
    second_labels = [text.get_text() for text in fig.axes[0].get_legend().get_texts()]

    assert first_labels == ["A", "B"]
    assert second_labels == ["A", "B"]


def test_comparison_legend_can_be_hidden_explicitly() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from core.comparison import render_comparison
    from core.types import ComparisonItem, PreparedSeries, SegmentInfo

    seg = SegmentInfo(index=0, start=0, end=2)
    prepared = PreparedSeries(
        raw_e=np.array([0.0, 1.0]),
        raw_j=np.array([1.0, 2.0]),
        e=np.array([0.0, 1.0]),
        j=np.array([1.0, 2.0]),
        eta=np.array([0.0, 1.0]),
        e_label="E",
        j_label="j",
        tafel_y_label="eta",
        potential_channel="E",
        current_channel="j",
        potential_formula="[E]",
        current_formula="[j]",
        e_eq=0.0,
        segment=seg,
    )
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    app = SimpleNamespace(
        fig=fig,
        canvas=canvas,
        _app_state={
            "comparison_items": [
                ComparisonItem(
                    item_id="a",
                    file_path=Path("a.cor"),
                    file_name="a",
                    segment_index=0,
                    prepared=prepared,
                    fit=None,
                    label="A",
                    color="#2563eb",
                )
            ],
            "comparison_highlight_row": -1,
            "comparison_lsv_style": "line_marker",
            "comparison_tafel_fit_window": False,
            "comparison_show_legend": False,
            "active_chart_mode": "comparison",
        },
    )

    render_comparison(app)

    assert fig.axes[0].get_legend() is None
    assert fig.axes[1].get_legend() is None
