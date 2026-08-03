import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import matplotlib.patheffects as patheffects
import os
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from io import BytesIO
from PIL import Image
from cartograpy.styling import load_cmap, get_available_palettes
import logging

logger = logging.getLogger(__name__)


def read_image(path, color=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".svg":
        # On lit le SVG comme texte
        with open(path, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # Si une couleur est spécifiée, on modifie tous les "fill"
        if color:
            import re

            # Change tous les attributs fill="..." par la nouvelle couleur
            svg_content = re.sub(r'fill="[^"]*"', f'fill="{color}"', svg_content)

        # On transforme la chaîne SVG en image
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(
            "w+", suffix=".svg", delete=False, encoding="utf-8"
        ) as tmp_svg:
            tmp_svg.write(svg_content)
            tmp_svg_path = tmp_svg.name

        try:
            drawing = svg2rlg(tmp_svg_path)
            buf = BytesIO()
            renderPM.drawToFile(drawing, buf, fmt="PNG")
            buf.seek(0)
            img = Image.open(buf)
        finally:
            os.remove(tmp_svg_path)
    else:
        img = Image.open(path)
    return img

def plot_choropleth(
    geodf,
    column_to_plot,
    label_column,
    label_title=None,
    title=None,
    cmap="rainbow",
    size=1.8,
    text_outline_color="white",
    text_outline_width=0,
    axes=True,
    grid=True,
    show_legend=True,
):
    """
    Crée une carte choroplèthe avec des étiquettes possédant un contour coloré.

    Paramètres:
    -----------
    geodf : GeoDataFrame
        Le GeoDataFrame à afficher
    column_to_plot : str
        Colonne numérique pour la colorisation
    label_column : str
        Colonne des étiquettes
    label_title : str, optional
        Titre de la barre de couleur
    title : str, optional
        Titre de la carte
    cmap : str, optional
        Palette de couleurs
    size : float, optional
        Taille de la figure
    text_outline_color : str, optional
        Couleur du contour des étiquettes
    text_outline_width : float, optional
        Largeur du contour des étiquettes

    Retourne:
    --------
    BytesIO
        L'image générée au format PNG
    """

    # Création du graphique
    if axes:
        fig = plt.figure(figsize=(10 * size, 8.5 * size))
        ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
    else:
        fig, ax = plt.subplots(figsize=(10 * size, 8.5 * size))
        ax.grid(False)
        ax.axis("off")
    # Normalisation des valeurs pour la colorisation
    vmin = geodf[column_to_plot].min()
    vmax = geodf[column_to_plot].max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = load_cmap(cmap)  # Correction ici

    # Ajout des labels ou étiquettes (avec contour) au centre des polygones
    for idx, row in geodf.iterrows():
        polygons = (
            [row.geometry]
            if row.geometry.geom_type == "Polygon"
            else list(row.geometry.geoms)
        )

        for poly in polygons:
            x, y = poly.exterior.xy
            ax.fill(
                x,
                y,
                color=cmap(norm(row[column_to_plot])),
                edgecolor="black",
                linewidth=0.5,
            )

            centroid = poly.centroid
            label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

            # Ajout du contour au texte
            ax.text(
                centroid.x,
                centroid.y,
                label_text,
                fontsize=10,
                ha="center",
                va="center",
                color="#0f172a",
                path_effects=[
                    patheffects.withStroke(  # Correction ici
                        linewidth=text_outline_width, foreground=text_outline_color
                    )
                ],
            )

    if show_legend:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(label_title or column_to_plot)

    plt.title(title, fontsize=20)
    plt.tight_layout()

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format="png")
    img_bytes.seek(0)
    return img_bytes
