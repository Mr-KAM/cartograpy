"""Tests for cartograpy.mapper.layout (multi-panel plate composition)."""
import pytest
import geopandas as gpd
from shapely.geometry import Polygon
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing
from matplotlib.patches import Patch  # noqa: E402

from cartograpy import Map, Layout  # noqa: E402


def _make_map(color="green", title="Panel"):
    m = Map(figsize=(3, 2), basemap=False, title=title)
    poly = Polygon([(-5, 4), (-3, 4), (-3, 6), (-5, 6)])
    gdf = gpd.GeoDataFrame({"val": [1]}, geometry=[poly], crs="EPSG:4326")
    m.add_polygons(gdf, facecolor=color, edge_color="black")
    m.legend_elements = [Patch(facecolor=color, edgecolor="black", label=f"{title} class")]
    return m


class TestLayoutInit:
    def test_default_template(self):
        layout = Layout("A4")
        assert layout._style == Layout.TEMPLATES["scientific"]

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError):
            Layout("A4", template="nonexistent")

    def test_unknown_paper_format_raises(self):
        with pytest.raises(ValueError):
            Layout("Z99")

    def test_explicit_figsize_tuple(self):
        layout = Layout((10, 6))
        assert layout.figsize == (10, 6)

    def test_orientation_swaps_dimensions(self):
        portrait = Layout("A4", orientation="portrait")
        landscape = Layout("A4", orientation="landscape")
        assert portrait.figsize == landscape.figsize[::-1]

    def test_background_override(self):
        layout = Layout("A4", template="minimal", background="black")
        assert layout._style["background"] == "black"

    def test_repr(self):
        layout = Layout("A4")
        assert "Layout" in repr(layout)


class TestLayoutTemplates:
    @pytest.mark.parametrize("template", sorted(Layout.TEMPLATES))
    def test_each_template_builds_and_exports(self, tmp_path, template):
        m1, m2 = _make_map("green", "A"), _make_map("blue", "B")
        layout = Layout("A4", orientation="landscape", template=template)
        layout.add_map(m1, caption="First")
        layout.add_map(m2, caption="Second")
        layout.add_title("Test plate")
        layout.add_legend()
        layout.add_source("Test source")
        layout.add_credits("Test credits")
        out = tmp_path / f"{template}.png"
        layout.export(str(out), dpi=60)
        assert out.exists()
        assert out.stat().st_size > 1000


class TestLayoutPanels:
    def test_grid_size(self):
        colors = ["green", "blue", "red", "orange"]
        maps = [_make_map(c) for c in colors]
        layout = Layout("A4")
        for m in maps:
            layout.add_map(m)
        nrows, ncols = layout._resolve_grid()
        assert nrows * ncols >= 4

    def test_explicit_position_grid(self):
        layout = Layout("A4", nrows=2, ncols=3)
        layout.add_map(_make_map(), position=(0, 0))
        layout.add_map(_make_map(), position=(1, 2), colspan=1)
        nrows, ncols = layout._resolve_grid()
        assert (nrows, ncols) == (2, 3)

    def test_single_panel_has_no_auto_label(self, tmp_path):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map())
        fig = layout._build()
        texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert not any(t.strip().startswith("(a)") for t in texts)

    def test_multi_panel_gets_sequential_labels(self):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map(), caption="One")
        layout.add_map(_make_map(), caption="Two")
        layout.add_map(_make_map(), caption="Three")
        fig = layout._build()
        texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("(a) One" in t for t in texts)
        assert any("(b) Two" in t for t in texts)
        assert any("(c) Three" in t for t in texts)

    def test_explicit_label_overrides_auto(self):
        # An explicit label is used verbatim (no auto lower/upper-casing).
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map(), caption="X")
        layout.add_map(_make_map(), caption="Y", label="Z")
        fig = layout._build()
        texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("(Z) Y" in t for t in texts)

    def test_show_label_false_forces_no_label(self):
        # With show_label=False, the caption is never drawn either since
        # it's only rendered alongside the panel label.
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map(), caption="One")
        layout.add_map(_make_map(), caption="Two", show_label=False)
        fig = layout._build()
        texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("(a) One" in t for t in texts)
        assert not any("Two" in t for t in texts)


class TestLayoutLegend:
    def test_auto_legend_merges_panel_handles(self):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map("green", "A"))
        layout.add_map(_make_map("blue", "B"))
        layout.add_legend()
        fig = layout._build()
        legend_ax = [ax for ax in fig.axes if ax.get_legend() is not None]
        assert len(legend_ax) == 1
        labels = [t.get_text() for t in legend_ax[0].get_legend().get_texts()]
        assert "A class" in labels
        assert "B class" in labels

    def test_explicit_handles_override_auto(self):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map("green", "A"))
        custom = [Patch(facecolor="red", label="Custom")]
        layout.add_legend(handles=custom)
        fig = layout._build()
        legend_ax = [ax for ax in fig.axes if ax.get_legend() is not None][0]
        labels = [t.get_text() for t in legend_ax.get_legend().get_texts()]
        assert labels == ["Custom"]

    def test_no_handles_warns_and_skips(self, caplog):
        layout = Layout("A4", template="scientific")
        m = Map(figsize=(3, 2), basemap=False)
        layout.add_map(m)
        layout.add_legend()
        fig = layout._build()
        assert all(ax.get_legend() is None for ax in fig.axes)


class TestLayoutOutput:
    def test_export_returns_path(self, tmp_path):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map())
        out = tmp_path / "out.png"
        result = layout.export(str(out), dpi=60)
        assert result == str(out)
        assert out.exists()

    def test_export_pdf(self, tmp_path):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map())
        out = tmp_path / "out.pdf"
        layout.export(str(out))
        assert out.exists() and out.stat().st_size > 0

    def test_export_svg(self, tmp_path):
        layout = Layout("A4", template="scientific")
        layout.add_map(_make_map())
        out = tmp_path / "out.svg"
        layout.export(str(out))
        assert out.exists() and out.stat().st_size > 0

    def test_panel_render_does_not_mutate_map_title(self, tmp_path):
        m = _make_map(title="Original")
        layout = Layout("A4", template="scientific")
        layout.add_map(m)
        layout.export(str(tmp_path / "out.png"), dpi=60)
        assert m.ax.get_title() == "Original"


class TestMapLayoutShortcut:
    def test_map_layout_returns_layout_with_one_panel(self):
        m = _make_map()
        layout = m.layout("minimal")
        assert isinstance(layout, Layout)
        assert len(layout._panels) == 1

    def test_map_layout_forwards_kwargs(self):
        m = _make_map()
        layout = m.layout("poster", paper_format="A3")
        assert layout._style == Layout.TEMPLATES["poster"]
