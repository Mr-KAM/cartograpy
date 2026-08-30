<img src="assets/img/logo.png" alt="Logo cartograpy" width="220">

# cartograpy

[![PyPI](https://img.shields.io/pypi/v/cartograpy.svg)](https://pypi.org/project/cartograpy/)
[![Python](https://img.shields.io/pypi/pyversions/cartograpy.svg)](https://pypi.org/project/cartograpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mr--kam.github.io-blue.svg)](https://mr-kam.github.io/cartograpy/)

Mapping in Python, the way it was always meant to be.

Cartograpy est un package Python pour charger, traiter et cartographier des
données géographiques en quelques lignes de code — des frontières
administratives d'un pays jusqu'à la carte statique finale, prête à exporter.

![Exemple de carte produite avec cartograpy](assets/img/create_python_maps.py.png)

## Fonctionnalités

- **Données** : téléchargez en une ligne des frontières administratives
  (`GeoBoundaries`), des données OpenStreetMap, hydrographiques, de
  géocodage, d'altitude (SRTM) ou des indicateurs World Bank.
- **Traitement** : importez/exportez tous les formats courants (Shapefile,
  GeoJSON, KML, GPX, GPKG, CSV, Parquet...), découpez, fusionnez, calculez
  des centroïdes et des attributs dynamiques.
- **Cartographie** : cartes choroplèthes, points, polygones, raster,
  bivariées ou hexbin avec la classe `Map` — flèche du nord, barre d'échelle,
  légendes, styles de police et palettes de couleurs personnalisables.

## Installation

```bash
pip install cartograpy
```

> [!NOTE]
> Utilisez un environnement virtuel pour éviter les conflits de dépendances
> (`venv`, `conda`, `pew`...).

## Démarrage rapide

```python
from cartograpy.data import Bound
from cartograpy.mapper import Map

bound = Bound()
civ = bound.get_admin("CIV", adm=0)  # frontières nationales, via GeoBoundaries

m = Map(title="Côte d'Ivoire")
m.add_polygons(civ, facecolor="lightyellow", edgecolor="black")
m.add_north_arrow()
m.add_scale_bar()
m.show()

m.save("cote-divoire.png", dpi=300)  # export prêt à imprimer
```

## Aller plus loin

La documentation complète (référence de l'API, guides pas-à-pas, exemples)
est disponible sur **[mr-kam.github.io/cartograpy](https://mr-kam.github.io/cartograpy/)**.

Pour une visite guidée interactive de toutes les fonctionnalités, voir le
notebook [`notebooks/README.ipynb`](notebooks/README.ipynb).

## Licence

MIT — voir [`LICENSE`](LICENSE).
