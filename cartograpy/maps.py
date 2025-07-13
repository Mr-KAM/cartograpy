import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from io import BytesIO
import cartopy.crs as ccrs
from pyfonts import load_google_font
import mpl_fontkit as fk


def plot_choropleth(geodf, column_to_plot, label_column, label_title=None, title=None, cmap='rainbow', size=1.8, text_outline_color='white', text_outline_width=0,axes=True, grid=True, show_legend=True):
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
    fig, ax = plt.subplots(figsize=(10*size, 8.5*size))
    if axes:
        if grid:
            ax.set_facecolor('#f8f9fa')
            ax.grid(True)
        else:
            ax.grid(False)
        ax.axis('off')
        ax = plt.axes(projection=ccrs.PlateCarree())
        # ax.set_global()
        # ax.coastlines(resolution='50m')
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
    else:
        ax.grid(False)
        ax.axis('off')
    # Normalisation des valeurs pour la colorisation
    vmin = geodf[column_to_plot].min()
    vmax = geodf[column_to_plot].max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.get_cmap(cmap)  # Correction ici

    # Ajout des labels ou étiquettes (avec contour) au centre des polygones
    for idx, row in geodf.iterrows():
        polygons = [row.geometry] if row.geometry.geom_type == 'Polygon' else list(row.geometry.geoms)

        for poly in polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, color=cmap(norm(row[column_to_plot])), edgecolor='black', linewidth=0.5)

            centroid = poly.centroid
            label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

            # Ajout du contour au texte
            ax.text(centroid.x,
                    centroid.y,
                    label_text,
                    fontsize=10,
                    ha='center',
                    va='center',
                    color='#0f172a',
                    path_effects=[patheffects.withStroke(  # Correction ici
                        linewidth=text_outline_width,
                        foreground=text_outline_color)])

    if show_legend:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(label_title or column_to_plot)

    plt.title(title, fontsize=20)
    plt.tight_layout()

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    return img_bytes


def plot_pointmap(geodf, column_to_plot, label_column=None, point_size=None,
                 label_title=None, title=None, cmap='rainbow', size=1.8,
                 text_outline_color='white', text_outline_width=2,
                 background_color='#f8f9fa', min_point_size=20, max_point_size=200):
    """
    Crée une carte de points avec des étiquettes possédant un contour coloré.

    Paramètres:
    -----------
    geodf : GeoDataFrame
        Le GeoDataFrame contenant les points à afficher
    column_to_plot : str
        Colonne numérique pour la colorisation des points
    label_column : str, optional
        Colonne des étiquettes (si None, aucune étiquette n'est affichée)
    point_size : str, optional
        Colonne numérique pour dimensionner les points (si None, taille fixe)
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
    background_color : str, optional
        Couleur de fond de la carte
    min_point_size : float, optional
        Taille minimale des points si dimensionnés selon une variable
    max_point_size : float, optional
        Taille maximale des points si dimensionnés selon une variable

    Retourne:
    --------
    BytesIO
        L'image générée au format PNG
    """

    # Création du graphique
    fig, ax = plt.subplots(figsize=(10*size, 8.5*size))
    ax.set_facecolor(background_color)
    ax.grid(False)
    ax.axis('off')

    # Normalisation des valeurs pour la colorisation
    vmin = geodf[column_to_plot].min()
    vmax = geodf[column_to_plot].max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.get_cmap(cmap)

    # Préparation des tailles de points si une colonne est spécifiée
    if point_size:
        size_min = geodf[point_size].min()
        size_max = geodf[point_size].max()
        size_norm = plt.Normalize(vmin=size_min, vmax=size_max)

        def get_point_size(value):
            # Calcul d'une taille proportionnelle entre min_point_size et max_point_size
            normalized = size_norm(value)
            return min_point_size + normalized * (max_point_size - min_point_size)
    else:
        # Taille fixe si aucune colonne de taille n'est spécifiée
        def get_point_size(value):
            return min_point_size

    # Tracé des points
    for idx, row in geodf.iterrows():
        # Extraction des coordonnées du point
        x, y = row.geometry.x, row.geometry.y

        # Colorisation selon la colonne spécifiée
        point_color = cmap(norm(row[column_to_plot]))

        # Tracé du point
        circle_size = get_point_size(row[point_size]) if point_size else min_point_size
        ax.scatter(x, y, s=circle_size, color=point_color,
                  edgecolor='black', linewidth=0.5, alpha=0.7)

        # Ajout des étiquettes si demandé
        if label_column:
            label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

            ax.text(x, y, label_text,
                   fontsize=10,
                   ha='center',
                   va='center',
                   color='#0f172a',
                   path_effects=[patheffects.withStroke(
                       linewidth=text_outline_width,
                       foreground=text_outline_color)])

    # Ajout de la barre de couleur
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label(label_title or column_to_plot)

    # Ajout d'une légende pour la taille si applicable
    if point_size:
        # Création de points de référence pour la légende
        sizes = [size_min, (size_min + size_max) / 2, size_max]
        handles = []
        labels = []

        for size_value in sizes:
            handles.append(plt.scatter([], [],
                         s=get_point_size(size_value),
                         color='gray',
                         edgecolor='black'))
            labels.append(f"{size_value:,.0f}")

        # Ajout de la légende
        legend = ax.legend(handles, labels,
                         title=point_size,
                         loc='lower right',
                         frameon=True,
                         framealpha=0.9)

    plt.title(title, fontsize=20)
    plt.tight_layout()

    # Sauvegarde de l'image
    img_bytes = BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    return img_bytes





def plot_pointmap2(geodf, column_to_plot, label_column=None, point_size=None,
                 label_title=None, title=None, cmap='rainbow', size=1.8,
                 text_outline_color='white', text_outline_width=2,
                 background_color='#f8f9fa', min_point_size=20, max_point_size=200,
                 show_polygons=True, polygon_alpha=0.2):
    """
    Crée une carte de points avec des étiquettes possédant un contour coloré.
    Si la géométrie est un polygone, utilise son centroïde pour le point.

    Paramètres:
    -----------
    geodf : GeoDataFrame
        Le GeoDataFrame à afficher (Points ou Polygones)
    column_to_plot : str
        Colonne numérique pour la colorisation des points
    label_column : str, optional
        Colonne des étiquettes (si None, aucune étiquette n'est affichée)
    point_size : str, optional
        Colonne numérique pour dimensionner les points (si None, taille fixe)
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
    background_color : str, optional
        Couleur de fond de la carte
    min_point_size : float, optional
        Taille minimale des points si dimensionnés selon une variable
    max_point_size : float, optional
        Taille maximale des points si dimensionnés selon une variable
    show_polygons : bool, optional
        Afficher les polygones en plus des centroïdes (si géométrie = polygone)
    polygon_alpha : float, optional
        Transparence des polygones (entre 0 et 1)

    Retourne:
    --------
    BytesIO
        L'image générée au format PNG
    """

    # Création du graphique
    fig, ax = plt.subplots(figsize=(10*size, 8.5*size))
    ax.set_facecolor(background_color)
    ax.grid(False)
    ax.axis('off')

    # Normalisation des valeurs pour la colorisation
    vmin = geodf[column_to_plot].min()
    vmax = geodf[column_to_plot].max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.get_cmap(cmap)

    # Préparation des tailles de points si une colonne est spécifiée
    if point_size:
        size_min = geodf[point_size].min()
        size_max = geodf[point_size].max()
        size_norm = plt.Normalize(vmin=size_min, vmax=size_max)

        def get_point_size(value):
            # Calcul d'une taille proportionnelle entre min_point_size et max_point_size
            normalized = size_norm(value)
            return min_point_size + normalized * (max_point_size - min_point_size)
    else:
        # Taille fixe si aucune colonne de taille n'est spécifiée
        def get_point_size(value):
            return min_point_size

    # Tracé des points et/ou polygones
    for idx, row in geodf.iterrows():
        geom = row.geometry
        point_color = cmap(norm(row[column_to_plot]))
        circle_size = get_point_size(row[point_size]) if point_size else min_point_size

        # Traitement différent selon le type de géométrie
        if geom.geom_type == 'Point':
            x, y = geom.x, geom.y
            ax.scatter(x, y, s=circle_size, color=point_color,
                      edgecolor='black', linewidth=0.5, alpha=0.7)

        elif geom.geom_type == 'Polygon':
            # Dessiner le polygone en transparence si demandé
            if show_polygons:
                x, y = geom.exterior.xy
                ax.fill(x, y, color=point_color, alpha=polygon_alpha,
                       edgecolor='black', linewidth=0.5)

            # Dessiner le centroïde
            centroid = geom.centroid
            ax.scatter(centroid.x, centroid.y, s=circle_size, color=point_color,
                      edgecolor='black', linewidth=0.5, alpha=0.7)
            x, y = centroid.x, centroid.y

        elif geom.geom_type == 'MultiPolygon':
            # Pour chaque polygone de la collection
            for poly in geom.geoms:
                if show_polygons:
                    x, y = poly.exterior.xy
                    ax.fill(x, y, color=point_color, alpha=polygon_alpha,
                           edgecolor='black', linewidth=0.5)

            # Dessiner le centroïde de la MultiPolygon complète
            centroid = geom.centroid
            ax.scatter(centroid.x, centroid.y, s=circle_size, color=point_color,
                      edgecolor='black', linewidth=0.5, alpha=0.7)
            x, y = centroid.x, centroid.y

        else:
            # Cas des autres types (LineString, etc.) - on utilise le centroïde
            centroid = geom.centroid
            ax.scatter(centroid.x, centroid.y, s=circle_size, color=point_color,
                      edgecolor='black', linewidth=0.5, alpha=0.7)
            x, y = centroid.x, centroid.y

        # Ajout des étiquettes si demandé
        if label_column:
            label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

            ax.text(x, y, label_text,
                   fontsize=10,
                   ha='center',
                   va='center',
                   color='#0f172a',
                   path_effects=[patheffects.withStroke(
                       linewidth=text_outline_width,
                       foreground=text_outline_color)])

    # Ajout de la barre de couleur
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label(label_title or column_to_plot)

    # Ajout d'une légende pour la taille si applicable
    if point_size:
        # Création de points de référence pour la légende
        sizes = [size_min, (size_min + size_max) / 2, size_max]
        handles = []
        labels = []

        for size_value in sizes:
            handles.append(plt.scatter([], [],
                         s=get_point_size(size_value),
                         color='gray',
                         edgecolor='black'))
            labels.append(f"{size_value:,.0f}")

        # Ajout de la légende
        legend = ax.legend(handles, labels,
                         title=point_size,
                         loc='lower right',
                         frameon=True,
                         framealpha=0.9)

    plt.title(title, fontsize=20)
    plt.tight_layout()

    # Sauvegarde de l'image
    img_bytes = BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    return img_bytes
