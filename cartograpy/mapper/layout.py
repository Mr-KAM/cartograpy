"""cartograpy.mapper.layout — multi-panel cartographic composition.

Assembles several already-built `Map` instances into a single printable
plate: page-level title, one shared legend, source/credits footer, an
optional logo, and automatic panel labels ("(a)", "B.", ...).

Each map panel is rasterized via `Map.to_image()` and placed on a fresh
matplotlib figure; the title, legend, panel labels and footer text stay
vector. This keeps Layout fully decoupled from each Map's own Figure/Axes
(Cartopy GeoAxes, colorbars and legends do not move safely across
figures), at the cost of the map panels themselves not being vector in
the exported PDF/SVG.
"""
from __future__ import annotations

import math
import string
from typing import Optional, List, Tuple, Union

import matplotlib.pyplot as plt
from PIL import Image

import logging

logger = logging.getLogger(__name__)


class Layout:
    """
    Composes several Map instances into a single multi-panel plate.

    Quick example
    --------------
    >>> layout = Layout("A4", orientation="landscape", template="scientific")
    >>> layout.add_map(map_location, caption="Study area")
    >>> layout.add_map(map_ndvi, caption="NDVI")
    >>> layout.add_map(map_landcover, caption="Land cover")
    >>> layout.add_map(map_change, caption="Change 2020-2024")
    >>> layout.add_title("Land cover change in the study area")
    >>> layout.add_legend()
    >>> layout.add_source("Sentinel-2, ESA")
    >>> layout.add_credits("Map: A. Kambou, 2026")
    >>> layout.export("plate.pdf")
    """

    #: Named visual presets. Each is a flat dict of style parameters
    #: consumed by `_build()`; see the "scientific" entry for every key.
    TEMPLATES = {
        "scientific": dict(
            background="white", font_family="sans-serif",
            margins=dict(left=0.04, right=0.04, top=0.02, bottom=0.02),
            panel_spacing=0.05,
            panel_border=True, panel_border_width=0.8, accent_color="#333333",
            panel_label_format="({letter})", panel_label_badge=False,
            panel_label_fontsize=11, panel_label_fontweight="bold",
            panel_label_color="#111111",
            title_band_height=0.09, title_band_color=None, title_align="left",
            title_fontsize=15, title_fontweight="bold", title_color="#111111",
            footer_band_height=0.07, footer_fontsize=8, footer_color="#555555",
            legend_fontsize=9, legend_frameon=False,
        ),
        "journal": dict(
            background="white", font_family="serif",
            margins=dict(left=0.05, right=0.05, top=0.03, bottom=0.03),
            panel_spacing=0.04,
            panel_border=True, panel_border_width=0.6, accent_color="#000000",
            panel_label_format="{LETTER}.", panel_label_badge=False,
            panel_label_fontsize=10, panel_label_fontweight="bold",
            panel_label_color="#000000",
            title_band_height=0.08, title_band_color=None, title_align="center",
            title_fontsize=14, title_fontweight="bold", title_color="#000000",
            footer_band_height=0.06, footer_fontsize=7.5, footer_color="#333333",
            legend_fontsize=8.5, legend_frameon=True,
        ),
        "thesis": dict(
            background="white", font_family="serif",
            # Extra left margin reserves a binding gutter.
            margins=dict(left=0.09, right=0.05, top=0.04, bottom=0.04),
            panel_spacing=0.06,
            panel_border=True, panel_border_width=0.6, accent_color="#444444",
            panel_label_format="({letter})", panel_label_badge=False,
            panel_label_fontsize=10, panel_label_fontweight="normal",
            panel_label_color="#222222",
            title_band_height=0.08, title_band_color=None, title_align="left",
            title_fontsize=13, title_fontweight="bold", title_color="#000000",
            footer_band_height=0.07, footer_fontsize=8, footer_color="#444444",
            legend_fontsize=9, legend_frameon=True,
        ),
        "atlas": dict(
            background="white", font_family="sans-serif",
            margins=dict(left=0.03, right=0.03, top=0.01, bottom=0.02),
            panel_spacing=0.03,
            panel_border=True, panel_border_width=1.2, accent_color="#0B3D91",
            panel_label_format="{LETTER}", panel_label_badge=True,
            panel_label_fontsize=12, panel_label_fontweight="bold",
            panel_label_color="white",
            title_band_height=0.1, title_band_color="#0B3D91", title_align="center",
            title_fontsize=18, title_fontweight="bold", title_color="white",
            footer_band_height=0.05, footer_fontsize=8, footer_color="#333333",
            legend_fontsize=9, legend_frameon=False,
        ),
        "report": dict(
            background="white", font_family="sans-serif",
            margins=dict(left=0.05, right=0.05, top=0.02, bottom=0.02),
            panel_spacing=0.05,
            panel_border=False, panel_border_width=0, accent_color="#1B7A6E",
            panel_label_format="({letter})", panel_label_badge=False,
            panel_label_fontsize=10, panel_label_fontweight="bold",
            panel_label_color="#1B7A6E",
            title_band_height=0.09, title_band_color="#1B7A6E", title_align="left",
            title_fontsize=16, title_fontweight="bold", title_color="white",
            footer_band_height=0.06, footer_fontsize=8, footer_color="#555555",
            legend_fontsize=9, legend_frameon=False,
        ),
        "poster": dict(
            background="white", font_family="sans-serif",
            margins=dict(left=0.02, right=0.02, top=0.01, bottom=0.01),
            panel_spacing=0.03,
            panel_border=True, panel_border_width=2, accent_color="#D7263D",
            panel_label_format="{LETTER}", panel_label_badge=True,
            panel_label_fontsize=22, panel_label_fontweight="bold",
            panel_label_color="white",
            title_band_height=0.12, title_band_color=None, title_align="center",
            title_fontsize=34, title_fontweight="bold", title_color="#111111",
            footer_band_height=0.04, footer_fontsize=12, footer_color="#333333",
            legend_fontsize=14, legend_frameon=False,
        ),
        "minimal": dict(
            background="white", font_family="sans-serif",
            margins=dict(left=0.02, right=0.02, top=0.01, bottom=0.01),
            panel_spacing=0.02,
            panel_border=False, panel_border_width=0, accent_color="#888888",
            panel_label_format="{letter}", panel_label_badge=False,
            panel_label_fontsize=9, panel_label_fontweight="normal",
            panel_label_color="#888888",
            title_band_height=0.0, title_band_color=None, title_align="left",
            title_fontsize=11, title_fontweight="normal", title_color="#333333",
            footer_band_height=0.03, footer_fontsize=6.5, footer_color="#999999",
            legend_fontsize=8, legend_frameon=False,
        ),
    }
    DEFAULT_TEMPLATE = "scientific"

    def __init__(
        self,
        paper_format: Union[str, Tuple[float, float]] = "A4",
        orientation: str = "landscape",
        template: Optional[str] = None,
        nrows: Optional[int] = None,
        ncols: Optional[int] = None,
        dpi: int = 300,
        background: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        paper_format : "A4", "A3", "B2"... (see `Map.PAPER_SIZES`) or an
                       explicit (width, height) tuple in inches.
        orientation   : "portrait" or "landscape" (ignored for tuple sizes).
        template      : one of `Layout.TEMPLATES` ("scientific", "journal",
                        "thesis", "atlas", "report", "poster", "minimal").
                        Defaults to "scientific".
        nrows, ncols  : force the panel grid shape; auto-inferred from the
                        added maps otherwise.
        dpi           : resolution used to rasterize map panels and to
                        export raster formats (PNG/JPEG).
        background    : overrides the template's page background color.
        """
        if template is not None and template not in self.TEMPLATES:
            available = ", ".join(sorted(self.TEMPLATES))
            raise ValueError(
                f"template '{template}' inconnu. Disponibles: {available}"
            )
        self._style = {
            k: (dict(v) if isinstance(v, dict) else v)
            for k, v in self.TEMPLATES[template or self.DEFAULT_TEMPLATE].items()
        }
        if background is not None:
            self._style["background"] = background

        self.dpi = dpi
        self.figsize = self._resolve_figsize(paper_format, orientation)
        self._nrows = nrows
        self._ncols = ncols

        self._panels: List[dict] = []
        self._title: Optional[dict] = None
        self._legend_spec: Optional[dict] = None
        self._footer_items: List[tuple] = []
        self._logo_spec: Optional[dict] = None
        self._auto_legend_handles: List = []
        self.fig = None

    @staticmethod
    def _resolve_figsize(paper_format, orientation) -> Tuple[float, float]:
        if isinstance(paper_format, tuple):
            return paper_format
        from .map import Map

        fmt = paper_format.upper()
        if fmt not in Map.PAPER_SIZES:
            available = ", ".join(sorted(Map.PAPER_SIZES))
            raise ValueError(
                f"Format de papier '{paper_format}' non supporté. "
                f"Formats disponibles: {available}"
            )
        width_mm, height_mm = Map.PAPER_SIZES[fmt]
        width_in, height_in = width_mm / 25.4, height_mm / 25.4
        if orientation.lower() == "portrait":
            return (width_in, height_in)
        elif orientation.lower() == "landscape":
            return (height_in, width_in)
        raise ValueError("orientation doit être 'portrait' ou 'landscape'")

    # ------------------------------------------------------------------ #
    # Declarative builders — cheap, deferred to export()/show()          #
    # ------------------------------------------------------------------ #

    def add_map(
        self,
        map_obj,
        position: Optional[Tuple[int, int]] = None,
        rowspan: int = 1,
        colspan: int = 1,
        rect: Optional[Tuple[float, float, float, float]] = None,
        caption: Optional[str] = None,
        label: Optional[str] = None,
        show_label: Optional[bool] = None,
        dpi: Optional[int] = None,
        **to_image_kwargs,
    ) -> "Layout":
        """
        Adds a map panel.

        Parameters
        ----------
        map_obj    : a `Map` (or `Map2D`) instance to rasterize into this panel.
        position   : (row, col) grid cell (0-indexed). Auto-placed in
                     reading order if omitted.
        rowspan, colspan : how many grid cells this panel occupies.
        rect       : explicit (left, bottom, width, height) in figure
                     fraction, bypassing the grid entirely.
        caption    : short text shown next to the panel label
                     (e.g. "NDVI" -> "(a) NDVI").
        label      : explicit panel letter/text, overriding auto-lettering.
        show_label : True/False to force the panel label on/off; by
                     default a label is shown only once the layout has
                     more than one panel (or `label` was given).
        dpi        : overrides the layout's `dpi` for this panel's render.
        to_image_kwargs : forwarded to `map_obj.to_image()` (e.g. `format`).
        """
        self._panels.append(dict(
            map=map_obj, position=position, rowspan=rowspan, colspan=colspan,
            rect=rect, caption=caption, label=label, show_label=show_label,
            dpi=dpi, to_image_kwargs=to_image_kwargs,
        ))
        self._auto_legend_handles.extend(getattr(map_obj, "legend_elements", []) or [])
        return self

    def add_title(self, text: str, subtitle: Optional[str] = None, **kwargs) -> "Layout":
        """Sets the page title (and optional subtitle), shown in the top band."""
        self._title = dict(text=text, subtitle=subtitle, kwargs=kwargs)
        return self

    def add_legend(
        self,
        handles: Optional[list] = None,
        labels: Optional[List[str]] = None,
        title: Optional[str] = None,
        ncol: Optional[int] = None,
        **kwargs,
    ) -> "Layout":
        """
        Adds one shared legend built from every panel's own legend
        elements (deduplicated by label), unless `handles` is given
        explicitly.
        """
        self._legend_spec = dict(handles=handles, labels=labels, title=title,
                                  ncol=ncol, kwargs=kwargs)
        return self

    def add_source(self, text: str, **kwargs) -> "Layout":
        """Adds a data-source line in the footer (bottom-left)."""
        self._footer_items.append(("source", text, kwargs))
        return self

    def add_credits(self, text: str, **kwargs) -> "Layout":
        """Adds a credits/author line in the footer (bottom-right)."""
        self._footer_items.append(("credits", text, kwargs))
        return self

    def add_logo(
        self,
        path: str,
        position: str = "top-right",
        size: float = 0.08,
        **kwargs,
    ) -> "Layout":
        """
        Places a logo image at a page corner.

        Parameters
        ----------
        path     : path to an image file (PNG with transparency works well).
        position : "top-left", "top-right", "bottom-left", or "bottom-right".
        size     : logo width, as a fraction of the page width.
        """
        self._logo_spec = dict(path=path, position=position, size=size, kwargs=kwargs)
        return self

    # ------------------------------------------------------------------ #
    # Build                                                              #
    # ------------------------------------------------------------------ #

    def _next_letters(self):
        """Yields 'a', 'b', ..., 'z', 'aa', 'ab', ... for auto-labeled panels."""
        letters = string.ascii_lowercase
        i = 0
        while True:
            if i < 26:
                yield letters[i]
            else:
                yield letters[i // 26 - 1] + letters[i % 26]
            i += 1

    def _resolve_grid(self):
        explicit = [p for p in self._panels if p["position"] is not None]
        if explicit:
            nrows = self._nrows or max(p["position"][0] + p["rowspan"] for p in explicit)
            ncols = self._ncols or max(p["position"][1] + p["colspan"] for p in explicit)
        else:
            n = max(len(self._panels), 1)
            ncols = self._ncols or max(1, math.ceil(math.sqrt(n)))
            nrows = self._nrows or max(1, math.ceil(n / ncols))
        return nrows, ncols

    def _merged_legend_handles(self):
        handles, seen = [], set()
        for h in self._auto_legend_handles:
            lbl = h.get_label()
            if lbl and not lbl.startswith("_") and lbl not in seen:
                seen.add(lbl)
                handles.append(h)
        return handles

    def _build(self):
        style = self._style
        fig = plt.figure(figsize=self.figsize, dpi=self.dpi)
        fig.patch.set_facecolor(style["background"])

        margins = style["margins"]
        top = 1.0 - margins["top"]
        bottom = margins["bottom"]
        left = margins["left"]
        right = 1.0 - margins["right"]

        title_h = 0.0
        if self._title is not None:
            title_h = style["title_band_height"] or 0.06
            top -= title_h

        footer_h = 0.0
        if self._footer_items or self._legend_spec is not None:
            footer_h = style["footer_band_height"]
            bottom += footer_h

        nrows, ncols = self._resolve_grid()
        gs = fig.add_gridspec(
            nrows, ncols,
            left=left, right=right, top=top, bottom=bottom,
            wspace=style["panel_spacing"], hspace=style["panel_spacing"],
        )

        multi_panel = len(self._panels) > 1
        letters = self._next_letters()
        auto_row, auto_col = 0, 0
        for panel in self._panels:
            if panel["rect"] is not None:
                ax = fig.add_axes(panel["rect"])
            else:
                if panel["position"] is not None:
                    r, c = panel["position"]
                else:
                    r, c = auto_row, auto_col
                    auto_col += 1
                    if auto_col >= ncols:
                        auto_col, auto_row = 0, auto_row + 1
                rs, cs = panel["rowspan"], panel["colspan"]
                ax = fig.add_subplot(gs[r:r + rs, c:c + cs])

            # Map.to_image(title=None) keeps whatever title is already set
            # on the map's own axes (it doesn't mean "no title"); blank it
            # for the panel render since Layout draws its own caption/label,
            # then restore it so the original Map is left untouched.
            m = panel["map"]
            original_title = m.ax.get_title()
            m.ax.set_title("")
            try:
                img = m.to_image(
                    dpi=panel["dpi"] or self.dpi, legend=False, title=None,
                    **panel["to_image_kwargs"],
                )
            finally:
                m.ax.set_title(original_title)
            ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(style["panel_border"])
                if style["panel_border"]:
                    spine.set_color(style["accent_color"])
                    spine.set_linewidth(style["panel_border_width"])

            show = panel["show_label"]
            if show is None:
                show = multi_panel or panel["label"] is not None
            if show:
                letter = panel["label"] or next(letters)
                self._draw_panel_label(ax, letter, panel["caption"], style)

        if self._title is not None:
            self._draw_title(fig, top, title_h, style)
        if self._footer_items or self._legend_spec is not None:
            self._draw_footer(fig, footer_h, style)
        if self._logo_spec is not None:
            self._draw_logo(fig, style)

        self.fig = fig
        return fig

    def _draw_panel_label(self, ax, letter, caption, style):
        prefix = style["panel_label_format"].format(letter=letter, LETTER=letter.upper())
        common = dict(fontsize=style["panel_label_fontsize"],
                      fontweight=style["panel_label_fontweight"],
                      family=style["font_family"])
        if style["panel_label_badge"]:
            ax.text(0.06, 0.92, prefix, transform=ax.transAxes, va="center", ha="center",
                    color=style["panel_label_color"],
                    bbox=dict(boxstyle="circle,pad=0.4", facecolor=style["accent_color"],
                              edgecolor="none"),
                    **common)
            if caption:
                ax.text(0.14, 0.92, caption, transform=ax.transAxes, va="center", ha="left",
                        color=style["panel_label_color"] if style["panel_label_color"] != "white"
                        else style["accent_color"],
                        fontsize=style["panel_label_fontsize"] * 0.85,
                        family=style["font_family"])
        else:
            text = f"{prefix} {caption}" if caption else prefix
            ax.text(0.02, 0.96, text, transform=ax.transAxes, va="top", ha="left",
                    color=style["panel_label_color"], **common)

    @staticmethod
    def _hide_frame(ax):
        """
        Hides ticks/labels/spines without touching the axes background.
        `ax.axis("off")` looks equivalent but sets an internal flag that
        also skips drawing the axes patch entirely — which would make a
        colored title/footer band invisible however its facecolor is set.
        """
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    def _draw_title(self, fig, band_bottom, band_h, style):
        ax = fig.add_axes([0, band_bottom, 1, band_h])
        self._hide_frame(ax)
        if style["title_band_color"]:
            ax.set_facecolor(style["title_band_color"])
        else:
            ax.patch.set_alpha(0.0)
        x = 0.5 if style["title_align"] == "center" else self._style["margins"]["left"]
        ha = "center" if style["title_align"] == "center" else "left"
        y = 0.68 if self._title.get("subtitle") else 0.5
        title = self._title
        ax.text(x, y, title["text"], transform=ax.transAxes, ha=ha, va="center",
                fontsize=style["title_fontsize"], fontweight=style["title_fontweight"],
                color=style["title_color"], family=style["font_family"], **title["kwargs"])
        if title.get("subtitle"):
            ax.text(x, 0.28, title["subtitle"], transform=ax.transAxes, ha=ha, va="center",
                    fontsize=style["title_fontsize"] * 0.6, color=style["title_color"],
                    family=style["font_family"], style="italic")

    def _draw_footer(self, fig, band_h, style):
        ax = fig.add_axes([0, 0, 1, band_h])
        self._hide_frame(ax)
        ax.patch.set_alpha(0.0)

        legend_h_frac = 0.0
        if self._legend_spec is not None:
            spec = self._legend_spec
            handles = spec["handles"] or self._merged_legend_handles()
            if handles:
                ncol = spec["ncol"] or min(len(handles), 6)
                legend_kwargs = dict(
                    loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=ncol,
                    frameon=style["legend_frameon"], fontsize=style["legend_fontsize"],
                    title=spec["title"],
                )
                legend_kwargs.update(spec["kwargs"])
                if spec["labels"] is not None:
                    ax.legend(handles, spec["labels"], **legend_kwargs)
                else:
                    ax.legend(handles=handles, **legend_kwargs)
                legend_h_frac = 0.55
            else:
                logger.warning(
                    "Aucun élément de légende disponible pour la légende partagée."
                )

        text_y = legend_h_frac * 0.4 if legend_h_frac else 0.5
        margins = self._style["margins"]
        by_kind = {"source": [], "credits": []}
        for kind, text, _kwargs in self._footer_items:
            by_kind[kind].append(text)
        if by_kind["source"]:
            ax.text(margins["left"], text_y, " | ".join(by_kind["source"]),
                    transform=ax.transAxes, ha="left", va="bottom",
                    fontsize=style["footer_fontsize"], color=style["footer_color"],
                    family=style["font_family"])
        if by_kind["credits"]:
            ax.text(1 - margins["right"], text_y, " | ".join(by_kind["credits"]),
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=style["footer_fontsize"], color=style["footer_color"],
                    family=style["font_family"])

    def _draw_logo(self, fig, style):
        spec = self._logo_spec
        img = Image.open(spec["path"])
        w_frac = spec["size"]
        h_frac = w_frac * (img.height / img.width) * (self.figsize[0] / self.figsize[1])
        pad = 0.015
        pos = spec["position"]
        x = pad if "left" in pos else 1 - pad - w_frac
        y = pad if "bottom" in pos else 1 - pad - h_frac
        ax = fig.add_axes([x, y, w_frac, h_frac])
        ax.imshow(img)
        ax.axis("off")

    # ------------------------------------------------------------------ #
    # Output                                                             #
    # ------------------------------------------------------------------ #

    def show(self):
        """Builds and displays the layout (plt.show())."""
        self._build()
        plt.show()
        return self

    def export(self, path: str, dpi: Optional[int] = None, **kwargs) -> str:
        """
        Builds and saves the layout to `path` (format inferred from the
        extension: png, jpg, pdf, svg...).

        Returns
        -------
        str : the output path.
        """
        fig = self._build()
        fig.savefig(path, dpi=dpi or self.dpi, facecolor=self._style["background"], **kwargs)
        plt.close(fig)
        return path

    def __repr__(self) -> str:
        return f"Layout(panels={len(self._panels)}, figsize={self.figsize})"
