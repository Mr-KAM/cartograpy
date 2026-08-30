"""Tests pour le module mapper."""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from cartograpy.mapper import Map, Map2D, WebMap, SituationMap, read_image, plot_choropleth
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing


@pytest.fixture
def sample_gdf():
    return gpd.GeoDataFrame(
        {
            "name": ["A", "B"],
            "value": [10, 20],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            ],
        },
        crs="EPSG:4326",
    )


class TestMapClass:
    """Tests de la classe Map."""

    def test_paper_sizes_exist(self):
        assert "A4" in Map.PAPER_SIZES
        assert "A3" in Map.PAPER_SIZES
        assert "A0" in Map.PAPER_SIZES

    def test_paper_sizes_dimensions(self):
        w, h = Map.PAPER_SIZES["A4"]
        assert w == 210
        assert h == 297

    def test_instantiation_default(self):
        m = Map(verbose=False)
        assert m.title == ""  # pas de titre par défaut (cf. Map.__init__)
        assert m.fig is not None
        assert m.ax is not None
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_custom_title(self):
        m = Map(title="Test Map", verbose=False)
        assert m.title == "Test Map"
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_custom_figsize(self):
        m = Map(figsize=(10, 6), verbose=False)
        assert m.figsize == (10, 6)
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_paper_format(self):
        m = Map(figsize="A4", verbose=False)
        assert m.paper_info is not None
        assert m.paper_info["format"] == "A4"
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_layers_empty_initially(self):
        m = Map(verbose=False)
        assert m.layers == []
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_default_bounds(self):
        m = Map(verbose=False)
        assert m.bounds == [-180, -90, 180, 90]
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_add_scale_bar_renders_on_show(self, sample_gdf):
        # Régression : le layer scalebar était marqué "rendered" par le
        # rendu générique des layers point/line/polygon avant d'être
        # effectivement dessiné, donc jamais affiché.
        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_scale_bar(style="manual")
        n_artists_before = len(m.ax.texts) + len(m.ax.lines) + len(m.ax.patches)
        m._render(legend=False)
        n_artists_after = len(m.ax.texts) + len(m.ax.lines) + len(m.ax.patches)
        assert n_artists_after > n_artists_before
        assert m.layers[-1]["type"] == "scalebar"
        assert m.layers[-1]["rendered"] is True
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_add_scale_bar_manual_style_accepts_text_only_kwargs(self, sample_gdf):
        # Régression : le mode manuel filtrait les kwargs à passer à
        # ax.plot() (la ligne) avec une liste d'exclusion codée en dur
        # ("ha", "va", "fontweight") au lieu d'une liste d'inclusion —
        # tout autre kwarg destiné au texte (ex. font=, fontstyle=) fuitait
        # vers ax.plot() et plantait (Line2D n'accepte pas ces propriétés).
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        font = fm.FontProperties(family="monospace")
        m.add_scale_bar(style="manual", font=font, fontstyle="italic")
        m._render(legend=False)  # ne doit pas lever TypeError/AttributeError
        plt.close(m.fig)

    def test_add_scale_bar_to_fig_sets_figure_anchor(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_scale_bar(location="lower left", to="fig")
        m._render(legend=False)
        aob = m._scale_bar_artist._aob
        assert aob["bbox_to_anchor"] == (0.05, 0.05)  # défaut de `position`
        assert aob["bbox_transform"] is m.fig.transFigure
        plt.close(m.fig)

    def test_add_scale_bar_to_fig_custom_position(self, sample_gdf):
        # Régression : position= n'existait pas sur add_scale_bar, un
        # kwarg position= fuitait tel quel jusqu'à MmuScaleBar(**kwargs) et
        # plantait avec TypeError (paramètre inconnu).
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_scale_bar(style="ticks", to="fig", position=(0.05, 0.82))
        m._render(legend=False)  # ne doit pas lever TypeError
        aob = m._scale_bar_artist._aob
        assert aob["bbox_to_anchor"] == (0.05, 0.82)
        plt.close(m.fig)

    def test_add_scale_bar_to_ax_default_unchanged(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_scale_bar(location="lower left", to="ax")
        m._render(legend=False)
        aob = m._scale_bar_artist._aob
        assert aob["bbox_to_anchor"] is None
        assert aob["bbox_transform"] is None
        plt.close(m.fig)

    def test_add_scale_bar_font_map_utils_falls_back_to_scalebar(self, sample_gdf):
        # Régression : font= n'existait pas sur add_scale_bar (crash direct
        # avec style='ticks'/'boxes', TypeError depuis MmuScaleBar). Comme
        # matplotlib-map-utils ne supporte pas de police précise, une police
        # explicite doit basculer vers style='scalebar' (avec avertissement)
        # pour être réellement appliquée plutôt qu'ignorée en silence.
        from cartograpy.mapper._optional_deps import HAS_MAP_UTILS, HAS_MPL_SCALEBAR
        if not (HAS_MAP_UTILS and HAS_MPL_SCALEBAR):
            pytest.skip("matplotlib-map-utils et/ou matplotlib-scalebar non installés")

        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        font = fm.FontProperties(family="monospace")
        with pytest.warns(RuntimeWarning):
            m.add_scale_bar(style="ticks", font=font)
            m._render(legend=False)
        # Doit avoir basculé sur le backend matplotlib-scalebar
        assert type(m._scale_bar_artist).__module__.startswith("matplotlib_scalebar")
        plt.close(m.fig)

    def test_add_scale_bar_font_scalebar_style_applies_font(self, sample_gdf):
        from cartograpy.mapper._optional_deps import HAS_MPL_SCALEBAR
        if not HAS_MPL_SCALEBAR:
            pytest.skip("matplotlib-scalebar non installé")

        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        font = fm.FontProperties(family="monospace")
        m.add_scale_bar(style="scalebar", font=font, fontsize=14)
        m._render(legend=False)
        fp = m._scale_bar_artist.font_properties
        assert fp.get_family() == ["monospace"]
        assert fp.get_size() == 14
        plt.close(m.fig)

    def test_add_scale_bar_font_manual_style_applies_font(self, sample_gdf):
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import matplotlib.text as mtext

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        font = fm.FontProperties(family="monospace")
        m.add_scale_bar(style="manual", font=font)
        m._render(legend=False)
        m.fig.canvas.draw()
        families = [
            t.get_fontproperties().get_family()
            for t in m.fig.findobj(mtext.Text)
            if t.get_text().endswith("km")
        ]
        assert ["monospace"] in families
        plt.close(m.fig)

    def test_add_scale_bar_manual_style_to_fig_warns(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        with pytest.warns(RuntimeWarning):
            m.add_scale_bar(style="manual", to="fig")
            m._render(legend=False)
        plt.close(m.fig)

    def test_save_uses_own_figure_not_current_pyplot_figure(self, sample_gdf, tmp_path):
        # Régression : save() appelait plt.savefig() (figure "courante" de
        # pyplot) au lieu de self.fig.savefig() — si une autre Map est créée
        # entre-temps (cas courant en notebook), save() sauvegardait la
        # mauvaise figure alors que show() affichait la bonne.
        import matplotlib.pyplot as plt
        from PIL import Image

        m1 = Map(figsize=(4, 3), dpi=100, verbose=False)
        m1.add_polygons(sample_gdf)

        # Une deuxième Map devient la figure "courante" de pyplot.
        m2 = Map(figsize=(9, 7), dpi=100, verbose=False)
        m2.add_polygons(sample_gdf)
        assert plt.gcf() is m2.fig

        out = tmp_path / "m1.png"
        m1.save(str(out), dpi=100, bbox_inches=None, auto_extent=False)

        with Image.open(out) as img:
            width, height = img.size

        assert (width, height) == (400, 300)
        plt.close(m1.fig)
        plt.close(m2.fig)

    def test_add_scale_bar_default_map_utils_style_does_not_crash(self, sample_gdf):
        # Régression : major_div était forcé à 4 par défaut et transmis à
        # matplotlib-map-utils sans major_mult correspondant, ce qui fait
        # échouer son calcul auto de longueur de barre (_config_bar_length
        # retourne None -> "TypeError: cannot unpack non-iterable NoneType
        # object" au moment du dessin/affichage de la figure).
        from cartograpy.mapper._optional_deps import HAS_MAP_UTILS
        if not HAS_MAP_UTILS:
            pytest.skip("matplotlib-map-utils non installé")

        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_scale_bar()  # défauts : style="auto" -> matplotlib-map-utils
        m._render(legend=False)
        # Force le rendu complet (comme l'affichage IPython d'une figure).
        m.fig.canvas.draw()
        assert m._scale_bar_artist is not None
        plt.close(m.fig)

    def test_north_arrow_svg_size_normalized_across_icons(self):
        # Régression : les 17 SVG embarquées se rastérisent à des tailles
        # natives très différentes (de 5x16 à 580x580 px selon l'icône).
        # Sans normalisation, un même zoom=1 rendait certaines flèches
        # énormes (icônes 580x580) et d'autres minuscules. La taille
        # affichée (pixels natifs x zoom effectif) doit maintenant être la
        # même quelle que soit l'icône choisie.
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        arrow_files = m.get_north_arrows()
        assert len(arrow_files) >= 2

        displayed_sizes = []
        for i in range(1, len(arrow_files) + 1):
            m.add_north_arrow(arrow=i, style="svg")
            img = m._north_arrow_artist.offsetbox.get_data()
            zoom = m._north_arrow_artist.offsetbox.get_zoom()
            displayed_sizes.append(max(img.shape[:2]) * zoom)

        assert max(displayed_sizes) - min(displayed_sizes) < 1.0
        plt.close(m.fig)

    def test_add_inset_data_bbox(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_inset(data=[-8, 4, -2, 10])
        assert m._inset_ax is not None
        assert len(m._inset_ax.patches) == 1
        plt.close(m.fig)

    def test_add_inset_data_geodataframe_mode_geometry_vs_bbox(self, sample_gdf):
        import matplotlib.pyplot as plt

        m_bbox = Map(verbose=False)
        m_bbox.add_polygons(sample_gdf)
        m_bbox.add_inset(data=sample_gdf, mode="bbox")
        assert len(m_bbox._inset_ax.patches) == 1

        m_geom = Map(verbose=False)
        m_geom.add_polygons(sample_gdf)
        m_geom.add_inset(data=sample_gdf, mode="geometry")
        # add_geometries() n'ajoute pas de Patch mais une Collection
        assert len(m_geom._inset_ax.patches) == 0

        plt.close(m_bbox.fig)
        plt.close(m_geom.fig)

    def test_add_inset_on_draws_context_layer(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        n_before = len(m.ax.collections)
        m.add_inset(data=sample_gdf, on=sample_gdf, style="classic")
        # `on` est dessiné via GeoDataFrame.plot() sur l'axe de l'inset,
        # pas sur l'axe principal - on vérifie juste que l'inset a du contenu.
        assert m._inset_ax is not None
        plt.close(m.fig)

    def test_add_inset_rejects_bad_data_type(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        with pytest.raises(TypeError):
            m.add_inset(data="not-a-bbox-or-gdf")
        plt.close(m.fig)

    def test_add_inset_geometry_mode_with_bbox_data_warns_and_falls_back(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        with pytest.warns(RuntimeWarning):
            m.add_inset(data=[-8, 4, -2, 10], mode="geometry")
        assert len(m._inset_ax.patches) == 1
        plt.close(m.fig)

    def test_add_inset_default_unchanged(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_inset()  # data=None -> comportement hérité (self.bounds)
        assert m._inset_ax is not None
        plt.close(m.fig)

    def test_add_inset_zoom_to_on(self):
        # Régression : set_extent() attend (minx, maxx, miny, maxy), alors
        # que total_bounds/bounds internes sont en (minx, miny, maxx, maxy)
        # - un mélange des deux ordres donne une étendue transposée/fausse.
        import matplotlib.pyplot as plt

        africa = gpd.GeoDataFrame(
            {"name": ["africa"]},
            geometry=[Polygon([(-20, -35), (50, -35), (50, 37), (-20, 37)])],
            crs="EPSG:4326",
        )
        civ = gpd.GeoDataFrame(
            {"name": ["civ"]},
            geometry=[Polygon([(-8, 4), (-2, 4), (-2, 10), (-8, 10)])],
            crs="EPSG:4326",
        )

        m = Map(verbose=False)
        m.add_polygons(civ)
        m.add_inset(on=africa, zoom_to_on=True)
        x0, x1, y0, y1 = m._inset_ax.get_extent()
        assert (x0, x1, y0, y1) == pytest.approx((-20.0, 50.0, -35.0, 37.0))
        # Le cadre autour de l'étendue de `on` doit être dessiné.
        assert len(m._inset_ax.patches) >= 1
        plt.close(m.fig)

    def test_add_inset_zoom_to_on_without_on_warns(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        with pytest.warns(RuntimeWarning):
            m.add_inset(zoom_to_on=True)
        assert m._inset_ax is not None
        plt.close(m.fig)

    def test_add_inset_to_ax_vs_fig_differ(self, sample_gdf):
        import matplotlib.pyplot as plt

        m_ax = Map(verbose=False)
        m_ax.add_polygons(sample_gdf)
        m_ax.add_inset(location="lower right", to="ax")
        pos_ax = m_ax._inset_ax.get_position()

        m_fig = Map(verbose=False)
        m_fig.add_polygons(sample_gdf)
        m_fig.add_inset(location="lower right", to="fig")
        pos_fig = m_fig._inset_ax.get_position()

        assert (pos_ax.x0, pos_ax.y0) != (pos_fig.x0, pos_fig.y0)
        plt.close(m_ax.fig)
        plt.close(m_fig.fig)

    def test_add_inset_to_classic_style(self, sample_gdf):
        import matplotlib.pyplot as plt

        m_ax = Map(verbose=False)
        m_ax.add_polygons(sample_gdf)
        m_ax.add_inset(style="classic", position=(0.65, 0.02, 0.33, 0.33), to="ax")
        pos_ax = m_ax._inset_ax.get_position()

        m_fig = Map(verbose=False)
        m_fig.add_polygons(sample_gdf)
        m_fig.add_inset(style="classic", position=(0.65, 0.02, 0.33, 0.33), to="fig")
        pos_fig = m_fig._inset_ax.get_position()

        assert (pos_ax.x0, pos_ax.y0) != (pos_fig.x0, pos_fig.y0)
        plt.close(m_ax.fig)
        plt.close(m_fig.fig)

    def test_add_inset_rejects_bad_to(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        with pytest.raises(ValueError):
            m.add_inset(to="bad")
        plt.close(m.fig)

    def test_add_inset_circular_true_produces_round_boundary(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_inset(circular=True)
        # `set_boundary` remplace le patch rectangulaire (4-5 sommets) par
        # un polygone à haute résolution (100 points) approximant un cercle.
        assert m._inset_ax.patch.get_path().vertices.shape[0] > 50
        plt.close(m.fig)

    def test_add_inset_circular_false_keeps_rectangular_boundary(self, sample_gdf):
        import matplotlib.pyplot as plt

        m = Map(verbose=False)
        m.add_polygons(sample_gdf)
        m.add_inset(circular=False)
        assert m._inset_ax.patch.get_path().vertices.shape[0] <= 10
        plt.close(m.fig)

    def test_add_inset_circular_is_actually_round_not_elliptical(self, sample_gdf):
        # Régression : l'ajustement d'aspect d'une GeoAxes est paresseux
        # (n'est correct qu'après un draw()) — sans forcer un draw avant de
        # mesurer get_position(), le cercle calculé serait légèrement
        # elliptique une fois rendu pour de vrai.
        import matplotlib.pyplot as plt

        m = Map(figsize=(12, 6), verbose=False)
        m.add_polygons(sample_gdf)
        m.add_inset(circular=True, size=(3, 2))
        m.fig.canvas.draw()

        patch = m._inset_ax.patch
        verts = patch.get_path().transformed(patch.get_transform()).vertices
        w = verts[:, 0].max() - verts[:, 0].min()
        h = verts[:, 1].max() - verts[:, 1].min()
        assert w / h == pytest.approx(1.0, abs=0.01)
        plt.close(m.fig)


class TestAddCustomLabels:
    """Tests de Map.add_custom_labels()."""

    @staticmethod
    def _gdf():
        from shapely.geometry import Point
        return gpd.GeoDataFrame(
            {
                "nom": ["A", "B", "C"],
                "val": [10.4, 20.6, 30.1],
                "geometry": [
                    Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                    Polygon([(2, 2), (3, 2), (3, 3), (2, 3)]),
                    Point(5, 5),
                ],
            },
            crs="EPSG:4326",
        )

    @staticmethod
    def _n_labels(ax):
        from matplotlib.offsetbox import AnnotationBbox
        return sum(isinstance(c, AnnotationBbox) for c in ax.get_children())

    def test_labels_one_text_per_entity(self):
        import matplotlib.pyplot as plt
        m = Map(basemap=False, verbose=False)
        n_before = self._n_labels(m.ax)
        out = m.add_custom_labels(self._gdf(), "<{nom}>: {val:.0f}")
        assert out is m
        assert self._n_labels(m.ax) - n_before == 3  # une étiquette par entité
        plt.close(m.fig)

    def test_except_skips_listed_values(self):
        import matplotlib.pyplot as plt
        m = Map(basemap=False, verbose=False)
        n_before = self._n_labels(m.ax)
        m.add_custom_labels(
            self._gdf(), "{nom}", except_=("nom", ["A", "C"]),
        )
        assert self._n_labels(m.ax) - n_before == 1  # seul "B" reste
        plt.close(m.fig)

    def test_missing_column_raises_keyerror(self):
        import matplotlib.pyplot as plt
        m = Map(basemap=False, verbose=False)
        with pytest.raises(KeyError):
            m.add_custom_labels(self._gdf(), "{does_not_exist}")
        plt.close(m.fig)

    def test_bad_except_shape_raises(self):
        import matplotlib.pyplot as plt
        m = Map(basemap=False, verbose=False)
        with pytest.raises(ValueError):
            m.add_custom_labels(self._gdf(), "{nom}", except_="nom")
        plt.close(m.fig)


class TestMap2D:
    """Tests de la classe Map2D."""

    def test_inherits_map(self):
        assert issubclass(Map2D, Map)

    def test_instantiation(self):
        m = Map2D(verbose=False)
        assert m.fig is not None
        import matplotlib.pyplot as plt
        plt.close(m.fig)


class TestWebMap:
    """Tests de la classe WebMap."""

    def test_instantiation(self):
        wm = WebMap()
        assert wm is not None

    def test_has_map_attribute(self):
        wm = WebMap()
        # WebMap wraps folium.Map
        assert hasattr(wm, "m") or hasattr(wm, "map")


class TestSituationMap:
    """Tests de la classe SituationMap."""

    def test_instantiation(self):
        sm = SituationMap(verbose=False)
        assert sm is not None
        assert sm.fig is not None
        import matplotlib.pyplot as plt
        plt.close(sm.fig)

    def test_custom_title(self):
        sm = SituationMap(title="Test", verbose=False)
        assert sm.figsize == (14, 10)
        import matplotlib.pyplot as plt
        plt.close(sm.fig)

    def test_add_scale_bar_default_does_not_crash(self):
        # Même régression que Map._draw_scale_bar : major_div forcé sans
        # major_mult, et PlateCarree non résolue en "degree" par pyproj.
        from cartograpy.mapper._optional_deps import HAS_MAP_UTILS
        if not HAS_MAP_UTILS:
            pytest.skip("matplotlib-map-utils non installé")

        import matplotlib.pyplot as plt

        sm = SituationMap(verbose=False)
        sm.add_scale_bar()
        sm.fig.canvas.draw()
        plt.close(sm.fig)


class TestPlotChoropleth:
    """Tests de la fonction plot_choropleth."""

    def test_callable(self):
        assert callable(plot_choropleth)

    def test_basic_call(self, sample_gdf):
        import matplotlib.pyplot as plt
        # Should not raise
        plot_choropleth(
            sample_gdf,
            column_to_plot="value",
            label_column="name",
            title="Test",
        )
        plt.close("all")


class TestReadImage:
    """Tests de la fonction read_image."""

    def test_callable(self):
        assert callable(read_image)

    def test_read_png(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (10, 10), "red")
        path = tmp_path / "test.png"
        img.save(str(path))
        result = read_image(str(path))
        assert result is not None
        assert result.size == (10, 10)

    def test_read_svg_preserves_transparency(self):
        # Régression : le fond des SVG rastérisées (flèches du Nord, logos)
        # était blanc opaque au lieu de transparent, ce qui masquait la
        # carte sous un carré blanc plein une fois l'icône ajoutée.
        import numpy as np
        from cartograpy.mapper.map import Map

        m = Map(verbose=False)
        arrow_path = m.get_north_arrows()[0]
        img = read_image(arrow_path, color="black")
        assert img.mode == "RGBA"

        arr = np.asarray(img)
        alpha = arr[:, :, 3]
        # Le fond (hors glyphe) doit être transparent, pas seulement le
        # glyphe opaque : les deux catégories doivent être présentes.
        assert (alpha == 0).any()
        assert (alpha == 255).any()
        import matplotlib.pyplot as plt
        plt.close(m.fig)
