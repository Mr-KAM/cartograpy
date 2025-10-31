<center> 
<img src="data/logo.png" alt="Logo" style="width: 30vw;min-width:200px">

<p>
Mapping in Python, the way it was always meant to be.
</p> 
</center>

# **PRESENTATION**

Cartograpy est un package Python conçu pour faciliter la manipulation de
données géographiques et la création de cartes de manière simple et
intuitive. Grâce à ses nombreuses fonctionnalités, il permet aussi bien
aux débutants qu’aux experts de visualiser, analyser et mettre en valeur
des données spatiales en quelques lignes de code.

<img src="data\create_python_maps.py.png" alt="Logo" style="min-width:300px;max-width:550px; width:60vw">
<p>
And you have all you need !
</p>

# **FONCTIONNALITES**

Voici ce que vous pouvez faire avec `cartograpy`:

## **Téléchargement et accès rapide aux données géographiques**

- **Découpages administratifs** : Téléchargez en une ligne les limites
  administratives de n’importe quel pays, région ou commune.
- **Données de continents** : Récupérez facilement les frontières
  vectorielles des continents ou sous-continents.
- **Réseaux hydrographiques** : Accédez à des couches de rivières,
  fleuves ou plans d’eau.
- **Géocodage des localités** : Enrichissez vos jeux de données en
  rétrouvant des zones géographiques associées à des adresses ou des
  noms de lieux.

## **Pre-processing et processing des données**

- **Importez** tout type de données vectorielles ou matricielles :
  Shapefile, GeoJSON, KML, GPX, GPKG, CSV, Parquet, etc.
- **Exportez** vos analyses dans le format de votre choix, prêt pour
  QGIS, ArcGIS ou le web.
- **Listing automatique** : Repérez en un coup d’œil tous les fichiers
  géographiques présents dans un dossier.
- **Convertissez** vos jeux de données entre tous les formats courants
  en une seule commande.
- **Calculs de centroïdes**, jointures spatiales et attributaires,
  fusion de tables, création de nouveaux attributs dynamiquement à
  partir d’expressions Python.
- **Manipulation de DataFrame et GeoDataFrame** pour l’analyse de
  données géographiques.
- **Découpage de données vectoriel** par emprise ou par masque.

## **Cartographie et visualisation**

- **Créez des cartes personnalisées** (choroplèthes, points,
  polygones, tuiles raster, etc.) à l’aide de la classe puissante
  `Map`.
- **Ajoutez des éléments de style** : flèches du nord, barres
  d’échelle, graticules, labels, titres personnalisés, palettes de
  couleurs, etc.
- **Gérez vos légendes** et choisissez parmi plusieurs styles adaptés
  (scientifique, épuré, académique…).
- **Exportez vos cartes** directement en PNG, SVG ou autres formats.
- **Accédez à des styles de polices et de nombreuses palettes de
  couleurs**, y compris les palettes personnalisées, Seaborn et
  Matplotlib .

# **INSTALLATION**

Pour installer le package cartograpy, vous pouvez utiliser pip. Ouvrez
votre terminal ou invite de commande et exécutez la commande suivante :

```bash
pip install cartograpy
```

> \[!NOTE\]
>
> Pour eviter les conflits de dépendences, utilisez un environnement
> virtuel. Vous pouvez le faire avec pew ou virtual env ou anaconda.
> J’utilise très souvant `pew` pour cela.
>
> ```bash
> pip install pew
> pip new myenv
> pew workon myenv
> pip install cartograpy
> ```

# **UTILISATION**

cartograpy est composé de 4 modules principaux : - **data** : pour
l’obtention des données - **processing** : pour le traitement des
données - **mapper** : pour la visualisation des données sur une carte -
**styling** : pour la mise en forme de la carte

<figure class=''>

`<img src="test_files\figure-markdown_strict\mermaid-figure-1.png" style="width:11.36in;height:2.06in" />`

</figure>

## **Obtension de données géographiques**

Pour télécharger simplements des données dans cartograpy, vous devez
utiliser le module `data`. Il existe présentement cinq (5) types de
données que vous pouvez telecharger avec cartograpy : - les limites des
continents et le découpage administratif des pays (class
GeoBoundaries) - des données par le géocodage (class Geocoder) - des
données libres d’OSM, écoles, batiments, routes, hopitaux… (class OSM) -
des données hydrographiques (class Hydro) - des données de la la
WorldBank, differents indicateurs de différentes sources (class
WorldBank)

Ces ressources permettent un gain considérable de temps et facilitent la
création de vos cartes.

<figure class=''>

`<img src="test_files\figure-markdown_strict\mermaid-figure-4.png" style="width:15in;height:3.06in" />`

</figure>

Toutes les données sont formatées pour être retournées sous forme de
`GeoDataFrame` ou de `DataFrame`, afin d’en faciliter la manipulation.

Vous devez commencer par importer `data` de `cartograpy` de la manière
suivante :

```python
from cartograpy import data
```

> \[!NOTE\]
>
> Toutes les données proposées par le module `data` sont téléchargées en
> ligne. Assurez-vous donc d’avoir un accès à Internet lors de
> l’exécution.

### **Récupérer les limites de continents ou les limites administratives de pays**

Commencez par créer un objet de la classe `GeoBoundaries`, disponible
dans le module `data`.

```python
bound = data.GeoBoundaries()
```

#### **Telecharger les limites des continents**

Vous pouvez commencer par consulter la liste des noms de continents
disponibles avec la méthode `list_continents_names`.

```python
bound.list_continents_names()
```

    {'africa': 'Africa',
     'afrique': 'Africa',
     'asia': 'Asia',
     'asie': 'Asia',
     'europe': 'Europe',
     'north america': 'North America',
     'amérique du nord': 'North America',
     'south america': 'South America',
     'amérique du sud': 'South America',
     'oceania': 'Oceania',
     'océanie': 'Oceania',
     'antarctica': 'Antarctica',
     'antarctique': 'Antarctica'}

Pour obtenir une geodataframe des continents, vous pouvez utiliser la
méthode `continents`

```python
world = bound.continents() # World ici est une geodataframe des continents
world.head()
```

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">continent</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>Africa</td>
<td>MULTIPOLYGON (((-11.43878 6.78592, -11.70819 6...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>Antarctica</td>
<td>MULTIPOLYGON (((-61.13898 -79.98137, -60.61012...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>Asia</td>
<td>MULTIPOLYGON (((48.67923 14.0032, 48.23895 13....</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>Europe</td>
<td>MULTIPOLYGON (((-53.55484 2.3349, -53.77852 2....</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>North America</td>
<td>MULTIPOLYGON (((-155.22217 19.23972, -155.5421...</td>
</tr>
</tbody>
</table>

</div>

```python
# Vous pouvez la visualiser facilement en utilsant 'plot()' de geopandas
world.plot()
```

![](test_files/figure-markdown_strict/cell-6-output-1.png)

Si vous souhaitez obtenir la limite d’un seul continent, il vous suffit
de passer son nom en paramètre. Dans l’exemple ci-dessous, on récupère
la limite de l’Afrique.

```python
africa=bound.continents("africa")
africa.plot()
```

![](test_files/figure-markdown_strict/cell-7-output-1.png)

Si vous souhaitez obtenir la limite de plusieurs continents, il vous
suffit de passer leur liste en paramètre. Dans l’exemple ci-dessous, on
récupère la limite de l’Afrique et de l’Asie.

```python
africa_asia=bound.continents(["africa","asia"])
africa_asia.plot()
```

![](test_files/figure-markdown_strict/cell-8-output-1.png)

#### **Telecharger les limites administratifs de pays**

Pour télécharger les données des limites administratives d’un pays, vous
aurez besoin de deux paramètres importants : le nom du pays et le niveau
de subdivision administrative souhaité (`adminlevel`).

**Les noms de pays et code iso :**

Les codes des pays sont conformes à la norme ISO 3166-1 alpha-3. Pour
obtenir la liste des pays valides, vous pouvez utiliser la méthode
`list_countries()` de l’objet `GeoBoundaries`. L’exemple si dessous
renvoi la liste des 10 premiers noms pays.

```python
# Affiche les 10 premiers pays
bound.list_countries()[0:10]
```

    ['أفغانستان',
     'афганистан',
     'afghánistán',
     'afghanistan',
     'αφγανιστάν',
     'afganio',
     'afganistán',
     'afganistan',
     'afganisztán',
     'աֆղանստան']

Vous pouvez également rechercher le code ISO d’un pays en utilisant la
méthode `get_iso3`. Dans l’exemple suivant, on essaye d’obtenir le code
ISO de tous les pays contenant le mot-clé « burk ». La méthode renvoie
le code ISO3 du Burkina Faso, car c’est le seul pays trouvé.

```python
# Pour obtenir le code iso de tous les pays du monde contenant le mot clé "burk"
bound.get_iso3("burk")
```

    'BFA'

Si plusieurs pays correspondent, elle retourne une liste de tuples (nom
du pays, code ISO3).

```python
bound.get_iso3("con")  # Exemple pour obtenir le code ISO d'un pays
```

    [('congo', 'cog'),
     ('república del congo', 'cog'),
     ('république du congo', 'cog'),
     ('rep. del congo', 'cog'),
     ('congo-brazzaville', 'cog'),
     ('república do congo', 'cog'),
     ('demokratiske republik congo', 'cod'),
     ('congo, democratic republic of the', 'cod'),
     ('república democrática del congo', 'cod'),
     ('république démocratique du congo', 'cod'),
     ('rd del congo', 'cod'),
     ('congo-kinshasa', 'cod'),
     ('república democrática do congo', 'cod'),
     ('republica democrată congo', 'cod')]

**Les niveaux de subdivisions administratives d’un pays :**

Il existe *cinq (5)* niveaux de subdivisions administratives
disponibles. Pour les afficher, utilisez la méthode `admLevels` comme
suit :

```python
print(bound.adminLevels())
```

| Niveau GeoBoundaries | Nom commun (FR)            | Nom commun (EN)       |
| -------------------- | -------------------------- | --------------------- |
| ADM0                 | Pays                       | Country               |
| ADM1                 | Région / État / Province | State / Region        |
| ADM2                 | Département / District    | District / County     |
| ADM3                 | Sous-préfecture / Commune | Subdistrict / Commune |
| ADM4                 | Village / Localité        | Village / Locality    |
| ADM5                 | Quartier / Secteur         | Neighborhood / Sector |

> \[!NOTE\]
>
> - Le nombre de niveaux dépend du pays. Certains pays s’arrêtent à
>   ADM2, d’autres vont jusqu’à ADM4 ou ADM5.
> - Le nom réel des subdivisions varie d’un pays à l’autre (ex. :
>   « State », « Region », « Province », « Department », etc.).
> - GeoBoundaries propose toujours au moins le niveau ADM0 (frontière
>   nationale).

Pour savoir si un niveau administratif est disponible pour un pays, vous
pouvez utiliser la méthode `is_valid_adm` de l’objet `GeoBoundaries`.
Voici un exemple :

```python
# Exemple pour vérifier si le niveau ADM1 est valide pour la Côte d'Ivoire
print(bound.is_valid_adm("CIV","ADM1"))
```

    True

```python
# Exemple pour vérifier le niveau admin minimum pour la Côte d'Ivoire
print(bound._get_smallest_adm("CIV")) 
```

    Smallest ADM level found for CIV : ADM3
    ADM3

Lorsque vous avez le nom d’un ou de plusieurs pays ainsi qu’un niveau de
subdivision administrative, vous pouvez alors télécharger les données.

**Télécharger les données administratives d’un pays:**

```python

# Exemple : Récupérer les données administratives des régions de la cote d'ivoire
civ_data = bound.adm("CIV", "ADM2")
civ_data.head()
```

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">geometry</th>
<th data-quarto-table-cell-role="th">shapeName</th>
<th data-quarto-table-cell-role="th">shapeISO</th>
<th data-quarto-table-cell-role="th">shapeID</th>
<th data-quarto-table-cell-role="th">shapeGroup</th>
<th data-quarto-table-cell-role="th">shapeType</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>POLYGON ((-4.68451 6.27179, -4.6868 6.26883, -...</td>
<td>Agneby-Tiassa</td>
<td></td>
<td>98640826B52449815511854</td>
<td>CIV</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>POLYGON ((-7.71925 9.07004, -7.72574 9.06397, ...</td>
<td>Bafing</td>
<td></td>
<td>98640826B37750272367318</td>
<td>CIV</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>POLYGON ((-6.19702 10.24246, -6.20038 10.24495...</td>
<td>Bagoue</td>
<td></td>
<td>98640826B26044148659027</td>
<td>CIV</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>MULTIPOLYGON (((-4.68451 6.27179, -4.68338 6.2...</td>
<td>Belier</td>
<td></td>
<td>98640826B5123145245776</td>
<td>CIV</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>POLYGON ((-6.70042 9.06196, -6.70118 9.05639, ...</td>
<td>Bere</td>
<td></td>
<td>98640826B43857880322183</td>
<td>CIV</td>
<td>ADM2</td>
</tr>
</tbody>
</table>

</div>

```python
civ_data.plot()
```

![](test_files/figure-markdown_strict/cell-16-output-1.png)

**Télécharger les données administratives de plusieurs pays:**

Assurez-vous que le niveau administratif (`adminLevel`) est bien
disponible pour tous les pays présents dans la liste à télécharger.

```python
# Exemple : Récupérer les limites administratives de plusieurs pays (senegal et mali ici)
countries_data = bound.adm(["SEN", "mali"], "ADM2")
countries_data["mali"].head()
```

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">geometry</th>
<th data-quarto-table-cell-role="th">shapeName</th>
<th data-quarto-table-cell-role="th">shapeISO</th>
<th data-quarto-table-cell-role="th">shapeID</th>
<th data-quarto-table-cell-role="th">shapeGroup</th>
<th data-quarto-table-cell-role="th">shapeType</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>POLYGON ((-7.92938 12.68171, -7.93554 12.68821...</td>
<td>Bamako</td>
<td></td>
<td>8926073B70420899930674</td>
<td>MLI</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>POLYGON ((1.32448 16.90639, 1.03227 16.61402, ...</td>
<td>Ansongo</td>
<td></td>
<td>8926073B56917716124995</td>
<td>MLI</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>POLYGON ((1.17767 17.69958, 1.15458 17.70648, ...</td>
<td>Bourem</td>
<td></td>
<td>8926073B86504284097699</td>
<td>MLI</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>POLYGON ((1.32448 16.90639, 1.65353 17.5735, 1...</td>
<td>Gao</td>
<td></td>
<td>8926073B84061132695750</td>
<td>MLI</td>
<td>ADM2</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>POLYGON ((1.31144 15.27381, 1.4716 15.28167, 1...</td>
<td>Menaka</td>
<td></td>
<td>8926073B3742503303790</td>
<td>MLI</td>
<td>ADM2</td>
</tr>
</tbody>
</table>

</div>

#### **Récupérer les métadonnées d’un territoire**

Pour aller plus loin que la simple récupération des limites
géographiques, vous pouvez également obtenir des informations
descriptives sur un territoire grâce à la méthode `metadata`. Par
exemple, le code ci-dessous permet de récupérer les métadonnées
associées au niveau national (`ADM0`) de la Côte d’Ivoire, en utilisant
son code ISO (`CIV`). Vous pouvez ensuite explorer les différentes
informations disponibles, comme le nom du territoire, sa superficie, son
code ISO, la source des données, etc.

```python

# Récupérer les métadonnées disponibles pour la Côte d'Ivoire
metadata_civ = bound.metadata("CIV", "ADM0")

print(list(metadata_civ.keys()))
```bash

['boundaryID', 'boundaryName', 'boundaryISO', 'boundaryYearRepresented', 'boundaryType', 'boundaryCanonical', 'boundarySource', 'boundaryLicense', 'licenseDetail', 'licenseSource', 'boundarySourceURL', 'sourceDataUpdateDate', 'buildDate', 'Continent', 'UNSDG-region', 'UNSDG-subregion', 'worldBankIncomeGroup', 'admUnitCount', 'meanVertices', 'minVertices', 'maxVertices', 'meanPerimeterLengthKM', 'minPerimeterLengthKM', 'maxPerimeterLengthKM', 'meanAreaSqKM', 'minAreaSqKM', 'maxAreaSqKM', 'staticDownloadLink', 'gjDownloadURL', 'tjDownloadURL', 'imagePreview', 'simplifiedGeometryGeoJSON']

```python
# Le continent
metadata_civ["Continent"]
```

    'Africa'

```python
# Sous région
metadata_civ["UNSDG-subregion"]
```

    'Western Africa'

```python
# Région 
metadata_civ["UNSDG-region"]
```

    'Sub-Saharan Africa'

```python
# Url de la prévisualisation de la carte du pays
url_img=metadata_civ["imagePreview"]
url_img
```

    'https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CIV/ADM0/geoBoundaries-CIV-ADM0-PREVIEW.png'

```python
# Afficher l'image de prévisualisation dans le notebook
from IPython.display import Image, display

try :
    display(Image(url=url_img))
except :
    print("Impossible d'afficher l'image.")
```

<img src="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CIV/ADM0/geoBoundaries-CIV-ADM0-PREVIEW.png"/>

### **Géocoder une ou plusieurs adresses**

Le géocodage permet de convertir des adresses en coordonnées
géographiques (latitude et longitude). Vous pouvez géocoder une ou
plusieurs adresses en utilisant les méthodes `geocode` et
`reverse_geocode` de l’objet `Geocoder`.

Commencez par creer un objet Geocoder :

```python
from cartograpy import data
geocoder= data.Geocoder()
```

Vous pouvez maintenant géocoder une ou plusieurs adresses.

#### **Géocodage**

La méthode `geocode` renvoie un tuple dont la première position est un
GeoDataFrame des adresses trouvées, et la deuxième une liste des
adresses non trouvées. Si une adresse n’est pas trouvée, elle est
simplement ignorée.

Le géocodage peut également être effectué sur plusieurs adresses à la
fois, en passant une liste d’adresses en paramètre.

**Géocoder une adresse**

```python
addresse = "bouaké"
resultat_geocode = geocoder.geocode(addresse)

# Adresse trouvée
resultat_geocode[0]
```

    Début du géocodage de 1 localité(s)...
    Géocodage terminé.

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">query</th>
<th data-quarto-table-cell-role="th">address</th>
<th data-quarto-table-cell-role="th">latitude</th>
<th data-quarto-table-cell-role="th">longitude</th>
<th data-quarto-table-cell-role="th">altitude</th>
<th data-quarto-table-cell-role="th">raw</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>bouaké</td>
<td>Bouaké, Gbêkê, Vallée du Bandama, Côte d’Ivoire</td>
<td>7.689021</td>
<td>-5.028355</td>
<td>0.0</td>
<td>{'place_id': 275820936, 'licence': 'Data © Ope...</td>
<td>POINT (-5.02836 7.68902)</td>
</tr>
</tbody>
</table>

</div>

```python
# Adresse non trouvée
resultat_geocode[1]
```

    []

**Geocoder une liste d’adresses**

```python
liste_adresses = ["Abidjan", "Yamoussoukro", "Bouaké", "Korhogo","Man CI", "","portbouet"]
resultat_geocode=geocoder.geocode(liste_adresses)

# Adresses trouvées
resultat_geocode[0]
```

    Début du géocodage de 7 localité(s)...
    Géocodage terminé.

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">query</th>
<th data-quarto-table-cell-role="th">address</th>
<th data-quarto-table-cell-role="th">latitude</th>
<th data-quarto-table-cell-role="th">longitude</th>
<th data-quarto-table-cell-role="th">altitude</th>
<th data-quarto-table-cell-role="th">raw</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>Abidjan</td>
<td>Abidjan, Côte d’Ivoire</td>
<td>5.320357</td>
<td>-4.016107</td>
<td>0.0</td>
<td>{'place_id': 275930228, 'licence': 'Data © Ope...</td>
<td>POINT (-4.01611 5.32036)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>Yamoussoukro</td>
<td>Yamoussoukro, Côte d’Ivoire</td>
<td>6.820007</td>
<td>-5.277603</td>
<td>0.0</td>
<td>{'place_id': 405334522, 'licence': 'Data © Ope...</td>
<td>POINT (-5.2776 6.82001)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>Bouaké</td>
<td>Bouaké, Gbêkê, Vallée du Bandama, Côte d’Ivoire</td>
<td>7.689021</td>
<td>-5.028355</td>
<td>0.0</td>
<td>{'place_id': 275820936, 'licence': 'Data © Ope...</td>
<td>POINT (-5.02836 7.68902)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>Korhogo</td>
<td>Korhogo, Poro, Savanes, Côte d’Ivoire</td>
<td>9.458070</td>
<td>-5.631629</td>
<td>0.0</td>
<td>{'place_id': 276083703, 'licence': 'Data © Ope...</td>
<td>POINT (-5.63163 9.45807)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>Man CI</td>
<td>Man, Tonkpi, Montagnes, Côte d’Ivoire</td>
<td>7.410258</td>
<td>-7.550372</td>
<td>0.0</td>
<td>{'place_id': 277270784, 'licence': 'Data © Ope...</td>
<td>POINT (-7.55037 7.41026)</td>
</tr>
</tbody>
</table>

</div>

```python
# Adresses non trouvée
resultat_geocode[1]
```

    ['', 'portbouet']

> \[!NOTE\]
>
> **Notez qu’une adresse peut ne pas être trouvé du fait de la connexion
> internet dans ce cas relancez la commande**

#### **Reverse géocodage**

Le reverse géocodage, ou géocodage inversé, consiste à convertir des
coordonnées géographiques (latitude et longitude) en une adresse ou un
lieu compréhensible par l’humain. Cette opération est particulièrement
utile lorsqu’on dispose d’un point sur une carte et qu’on souhaite
obtenir l’adresse correspondante, comme le nom de la rue, la ville ou
même des points d’intérêt à proximité. Le module `Geocoder` de
cartograpy propose une méthode dédiée pour effectuer facilement ce type
de requête à partir d’une ou plusieurs coordonnées. Il s’agit de la
méthode `reverse_geocode` et retourne la même chose que `geocode`.

```python
resultats_reverse=geocoder.reverse_geocode((48.8566, 2.3522))
```

    Début du géocodage inverse (coordonnées -> adresse) de 1 point(s)...
    Géocodage inverse (coordonnées -> adresse) terminé.

```python
# trouvé
resultats_reverse[0]
# On a ici les résulats de l'hotel de ville de Paris
```

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">query</th>
<th data-quarto-table-cell-role="th">address</th>
<th data-quarto-table-cell-role="th">latitude</th>
<th data-quarto-table-cell-role="th">longitude</th>
<th data-quarto-table-cell-role="th">altitude</th>
<th data-quarto-table-cell-role="th">raw</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>48.8566, 2.3522</td>
<td>Hôtel de Ville, Place de l'Hôtel de Ville, Qua...</td>
<td>48.856426</td>
<td>2.352528</td>
<td>0.0</td>
<td>{'place_id': 88106896, 'licence': 'Data © Open...</td>
<td>POINT (2.35253 48.85643)</td>
</tr>
</tbody>
</table>

</div>

```python
# Pas trouvé 
resultats_reverse[1]
```

    []

### **Télécharger des données hyrographiques**

La classe `Hydro` de cartograpy.data permet de télécharger facilement
les données de réseaux hydrographiques à l’échelle des continents, en
s’appuyant sur la base de données internationale **HydroRivers**. Grâce
à cette classe, vous pouvez accéder rapidement aux principaux cours
d’eau et réseaux hydrologiques d’un continent donné, ce qui facilite la
création de cartes thématiques, l’analyse des bassins versants ou
l’étude des ressources en eau à large échelle.

Vous pouvez commencer par créer un objet `Hydro`.

```python
from cartograpy import data
hydro=data.Hydro()
```

#### **Informations sur les variables disponibles**

Pour obtenir des informations sur les différentes variables de la
GeoDataFrame d’hydrorivers retournée, vous pouvez utiliser la méthode
`describe_variables()` de `Hydro`.

```python
print(hydro.describe_variables())
```

    📘 Description des variables HydroRIVERS :

| Nom            | Signification                    | Unité / Type         |
| -------------- | -------------------------------- | --------------------- |
| `HYRIV_ID`   | ID du tronçon                   | entier                |
| `NEXT_DOWN`  | ID du tronçon aval              | entier                |
| `MAIN_RIV`   | ID du fleuve principal           | entier                |
| `LENGTH_KM`  | Longueur du segment              | km (float)            |
| `DIST_DN_KM` | Distance jusqu'à l'embouchure   | km (float)            |
| `DIST_UP_KM` | Distance depuis la source        | km (float)            |
| `CATCH_SKM`  | Surface locale du bassin versant | km² (float)          |
| `UPLAND_SKM` | Surface totale en amont          | km² (float)          |
| `ENDORHEIC`  | 1 = bassin fermé, 0 = ouvert    | booléen (int)        |
| `DIS_AV_CMS` | Débit moyen                     | m³/s (float)         |
| `ORD_STRA`   | Ordre de Strahler                | entier                |
| `ORD_CLAS`   | Classe hiérarchique simplifiée | entier                |
| `ORD_FLOW`   | Ordre de flux                    | entier                |
| `HYBAS_L12`  | Code du bassin de niveau 12      | entier (catégorique) |

#### **Télécharger les données de réseau hydrographique**

Pour ce faire, vous devez utiliser la méthode `download` de `Hydro` et
lui passer le code de la région (continent) en paramètre.

**Liste des régions:**

```python
hydro.valid_regions
```

    ['af', 'as', 'au', 'eu', 'na', 'sa']

<table>
<thead>
<tr>
<th>Code</th>
<th>Région</th>
</tr>
</thead>
<tbody>
<tr>
<td>af</td>
<td>Afrique</td>
</tr>
<tr>
<td>as</td>
<td>Asie</td>
</tr>
<tr>
<td>au</td>
<td>Australie/Océanie</td>
</tr>
<tr>
<td>eu</td>
<td>Europe</td>
</tr>
<tr>
<td>na</td>
<td>Amérique du Nord</td>
</tr>
<tr>
<td>sa</td>
<td>Amérique du Sud</td>
</tr>
</tbody>
</table>

**Téléchargement des données**

```python
rivers_africa = hydro.download(region="af")  # Afrique
rivers_africa.head()
```

    Les données pour la région AF sont déjà présentes.

<div>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">HYRIV_ID</th>
<th data-quarto-table-cell-role="th">NEXT_DOWN</th>
<th data-quarto-table-cell-role="th">MAIN_RIV</th>
<th data-quarto-table-cell-role="th">LENGTH_KM</th>
<th data-quarto-table-cell-role="th">DIST_DN_KM</th>
<th data-quarto-table-cell-role="th">DIST_UP_KM</th>
<th data-quarto-table-cell-role="th">CATCH_SKM</th>
<th data-quarto-table-cell-role="th">UPLAND_SKM</th>
<th data-quarto-table-cell-role="th">ENDORHEIC</th>
<th data-quarto-table-cell-role="th">DIS_AV_CMS</th>
<th data-quarto-table-cell-role="th">ORD_STRA</th>
<th data-quarto-table-cell-role="th">ORD_CLAS</th>
<th data-quarto-table-cell-role="th">ORD_FLOW</th>
<th data-quarto-table-cell-role="th">HYBAS_L12</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>10000001</td>
<td>0</td>
<td>10000001</td>
<td>0.89</td>
<td>0.0</td>
<td>7.2</td>
<td>11.27</td>
<td>11.1</td>
<td>0</td>
<td>0.062</td>
<td>1</td>
<td>1</td>
<td>8</td>
<td>1120031210</td>
<td>LINESTRING (9.6625 37.325, 9.65625 37.33125)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>10000002</td>
<td>0</td>
<td>10000002</td>
<td>2.90</td>
<td>0.0</td>
<td>7.0</td>
<td>24.59</td>
<td>24.2</td>
<td>0</td>
<td>0.126</td>
<td>1</td>
<td>1</td>
<td>7</td>
<td>1120031210</td>
<td>LINESTRING (9.8 37.30833, 9.81042 37.31875, 9....</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>10000003</td>
<td>10000009</td>
<td>10000009</td>
<td>4.63</td>
<td>5.7</td>
<td>9.8</td>
<td>57.23</td>
<td>57.2</td>
<td>0</td>
<td>0.316</td>
<td>1</td>
<td>1</td>
<td>7</td>
<td>1120031210</td>
<td>LINESTRING (9.68542 37.27083, 9.68542 37.26458...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>10000004</td>
<td>10000009</td>
<td>10000009</td>
<td>0.69</td>
<td>5.7</td>
<td>5.4</td>
<td>11.11</td>
<td>11.1</td>
<td>0</td>
<td>0.061</td>
<td>1</td>
<td>2</td>
<td>8</td>
<td>1120031210</td>
<td>LINESTRING (9.71458 37.2375, 9.71458 37.24375)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>10000005</td>
<td>0</td>
<td>10000005</td>
<td>8.32</td>
<td>0.0</td>
<td>13.6</td>
<td>35.02</td>
<td>34.0</td>
<td>0</td>
<td>0.177</td>
<td>1</td>
<td>1</td>
<td>7</td>
<td>1120031210</td>
<td>LINESTRING (9.75 37.27708, 9.75625 37.27708, 9...</td>
</tr>
</tbody>
</table>

</div>

```python
rivers_africa.plot()
```

![](test_files/figure-markdown_strict/cell-36-output-1.png)

### **Télécharger données de OpenStreeMap**

**OpenStreetMap (OSM)** est une base de données cartographique mondiale,
collaborative et libre, qui recense de nombreux objets géographiques
(routes, bâtiments, points d’intérêt, etc.) à l’échelle mondiale.

La classe `OSM` du module `data` de cartograpy offre une interface
simple et puissante pour télécharger des données issues d’OpenStreetMap
(OSM) selon une grande variété de besoins.

Pour commencer, creez un objet `OSM`.

```python
from cartograpy import data
osm = data.OSM()
```

#### **Gérer et explorer les tags OSM**

La classe `OSM` fournit plusieurs méthodes pour faciliter la recherche
et la compréhension des tags OSM, qui définissent le type d’objets
géographiques à télécharger (bâtiments, routes, écoles, hôpitaux, etc.).
Ces outils facilitent la préparation des filtres à appliquer pour
récupérer les données OSM qui correspondent à votre projet.

- **`list_tags`** permet d’obtenir la liste des tags par grande
  famille (bâtiment, voirie, loisirs, etc.) :

```python
print(osm.list_tags('amenity'))  # Affiche les tags liés aux services publics
```

    ['amenity']

- **`search_tags`** permet de rechercher un mot-clé dans tous les tags
  pour trouver rapidement ce qui vous intéresse :

```python
print(osm.search_tags('hospital'))  # Recherche tous les tags relatifs aux hôpitaux
```

    {'building': {'description': 'Bâtiments et structures', 'matching_tags': {'building': ['hospital']}, 'example': {'building': 'house', 'building:levels': '2'}}, 'amenity': {'description': 'Services publics et commodités', 'matching_tags': {'amenity': ['hospital']}, 'example': {'amenity': 'restaurant', 'cuisine': 'french'}}}

- **`get_common_tag_combinations`** retourne des exemples de requêtes
  toutes prêtes pour les objets OSM les plus fréquents :

```python
print(osm.get_common_tag_combinations()['restaurants'])
```

    {'amenity': 'restaurant'}

#### **Télécharger les données OSM**

Une fois les tags identifiés, la méthode `get_data` vous permet de
télécharger les objets OSM d’intérêt pour une zone donnée, sous forme de
GeoDataFrame.

Il suffit de spécifier les tags OSM correspondant au type d’objet
recherché (bâtiments, routes, écoles, hôpitaux, etc.) ainsi que le type
de géométrie souhaité (points, polygons, lines ou all).

- Vous pouvez utiliser un **nom de lieu** :

```python
 # Exemple : télécharger toutes les écoles à Abidjan
schools = osm.get_data("Abidjan, Côte d'Ivoire", {"amenity": "school"}, data_type="points")
schools.head()
```

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">geometry</th>
<th data-quarto-table-cell-role="th">amenity</th>
<th data-quarto-table-cell-role="th">name</th>
<th data-quarto-table-cell-role="th">addr:city</th>
<th data-quarto-table-cell-role="th">addr:country</th>
<th data-quarto-table-cell-role="th">addr:state</th>
<th data-quarto-table-cell-role="th">addr:street</th>
<th data-quarto-table-cell-role="th">source</th>
<th data-quarto-table-cell-role="th">toilets:wheelchair</th>
<th data-quarto-table-cell-role="th">operator</th>
<th data-quarto-table-cell-role="th">...</th>
<th data-quarto-table-cell-role="th">addr:postbox</th>
<th data-quarto-table-cell-role="th">capacity</th>
<th data-quarto-table-cell-role="th">max_age</th>
<th data-quarto-table-cell-role="th">min_age</th>
<th data-quarto-table-cell-role="th">addr:full</th>
<th data-quarto-table-cell-role="th">fax</th>
<th data-quarto-table-cell-role="th">addr:pobox</th>
<th data-quarto-table-cell-role="th">height</th>
<th data-quarto-table-cell-role="th">start_date</th>
<th data-quarto-table-cell-role="th">type</th>
</tr>
<tr>
<th data-quarto-table-cell-role="th">element</th>
<th data-quarto-table-cell-role="th">id</th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
</tr>
</thead>
<tbody>
<tr>
<td rowspan="5" data-quarto-table-cell-role="th"
data-valign="top">node</td>
<td data-quarto-table-cell-role="th">452872059</td>
<td>POINT (-3.96766 5.35476)</td>
<td>school</td>
<td>Le Phénix</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">768587329</td>
<td>POINT (-4.08861 5.31753)</td>
<td>school</td>
<td>Collège Gloris</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">768587517</td>
<td>POINT (-4.07367 5.33721)</td>
<td>school</td>
<td>Institut Nelson Mandela Yop</td>
<td>Yopougon</td>
<td>CI</td>
<td>Abidjan</td>
<td>Rue O13</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">775786986</td>
<td>POINT (-3.95377 5.35125)</td>
<td>school</td>
<td>École maternelle</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">844756679</td>
<td>POINT (-3.99363 5.30375)</td>
<td>school</td>
<td>Collège Voltaire</td>
<td>Marcory</td>
<td>CI</td>
<td>Abidjan</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
</tbody>
</table>

<p>5 rows × 64 columns</p>
</div>

- Ou une **bounding box** :

```python
  # Télécharger tous les routets dans une zone définie par une bbox
import osmnx as ox
# Coordonnées approximatives du centre de Yamoussoukro
center = (6.8206, -5.2767)
# Distance en mètres au tour du centre de la ville
bbox = ox.utils_geo.bbox_from_point(center, dist=10000)

tags = {"highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "footway", "cycleway"]} # Pour les routes
highway = osm.get_data(bbox, tags, data_type="lines")
highway.head()
```

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">geometry</th>
<th data-quarto-table-cell-role="th">crossing</th>
<th data-quarto-table-cell-role="th">highway</th>
<th data-quarto-table-cell-role="th">name</th>
<th data-quarto-table-cell-role="th">maxspeed</th>
<th data-quarto-table-cell-role="th">surface</th>
<th data-quarto-table-cell-role="th">lanes</th>
<th data-quarto-table-cell-role="th">smoothness</th>
<th data-quarto-table-cell-role="th">source</th>
<th data-quarto-table-cell-role="th">noname</th>
<th data-quarto-table-cell-role="th">...</th>
<th data-quarto-table-cell-role="th">kerb</th>
<th data-quarto-table-cell-role="th">tactile_paving</th>
<th data-quarto-table-cell-role="th">mtb:scale</th>
<th data-quarto-table-cell-role="th">bridge</th>
<th data-quarto-table-cell-role="th">layer</th>
<th data-quarto-table-cell-role="th">shoulder</th>
<th data-quarto-table-cell-role="th">toll</th>
<th data-quarto-table-cell-role="th">turn:lanes</th>
<th data-quarto-table-cell-role="th">description</th>
<th data-quarto-table-cell-role="th">leisure</th>
</tr>
<tr>
<th data-quarto-table-cell-role="th">element</th>
<th data-quarto-table-cell-role="th">id</th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
</tr>
</thead>
<tbody>
<tr>
<td rowspan="5" data-quarto-table-cell-role="th"
data-valign="top">way</td>
<td data-quarto-table-cell-role="th">22716531</td>
<td>LINESTRING (-5.27977 6.79398, -5.27939 6.79396...</td>
<td>NaN</td>
<td>secondary</td>
<td>NaN</td>
<td>NaN</td>
<td>asphalt</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">22716532</td>
<td>LINESTRING (-5.24343 6.80558, -5.24436 6.80449...</td>
<td>NaN</td>
<td>tertiary</td>
<td>NaN</td>
<td>NaN</td>
<td>asphalt</td>
<td>4</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">22716533</td>
<td>LINESTRING (-5.26734 6.80102, -5.26735 6.80084...</td>
<td>NaN</td>
<td>tertiary</td>
<td>Rue de Sopim</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">22716535</td>
<td>LINESTRING (-5.25813 6.79231, -5.25813 6.79256...</td>
<td>NaN</td>
<td>residential</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>bad</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">22716538</td>
<td>LINESTRING (-5.26461 6.80095, -5.26457 6.80229...</td>
<td>NaN</td>
<td>residential</td>
<td>NaN</td>
<td>NaN</td>
<td>paved</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>...</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
</tr>
</tbody>
</table>

<p>5 rows × 47 columns</p>
</div>

```python
highway.plot()
```

![](test_files/figure-markdown_strict/cell-43-output-1.png)

- Ou un **GeoDataFrame polygonal** :

```python
# batiment de la région du béré
gdf = civ_data[civ_data["shapeName"]=="Belier"] # région du béré 
buildings = osm.get_data(gdf, {"building": "yes"}, data_type="polygons")
buildings.head()
```

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">geometry</th>
<th data-quarto-table-cell-role="th">addr:city</th>
<th data-quarto-table-cell-role="th">building</th>
<th data-quarto-table-cell-role="th">name</th>
<th data-quarto-table-cell-role="th">amenity</th>
<th data-quarto-table-cell-role="th">operator</th>
<th data-quarto-table-cell-role="th">religion</th>
<th data-quarto-table-cell-role="th">man_made</th>
<th data-quarto-table-cell-role="th">source</th>
<th data-quarto-table-cell-role="th">building:levels</th>
<th data-quarto-table-cell-role="th">denomination</th>
<th data-quarto-table-cell-role="th">shop</th>
<th data-quarto-table-cell-role="th">office</th>
<th data-quarto-table-cell-role="th">bus</th>
<th data-quarto-table-cell-role="th">public_transport</th>
<th data-quarto-table-cell-role="th">healthcare</th>
<th data-quarto-table-cell-role="th">townhall:type</th>
<th data-quarto-table-cell-role="th">government</th>
<th data-quarto-table-cell-role="th">content</th>
<th data-quarto-table-cell-role="th">type</th>
</tr>
<tr>
<th data-quarto-table-cell-role="th">element</th>
<th data-quarto-table-cell-role="th">id</th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th"></th>
</tr>
</thead>
<tbody>
<tr>
<td rowspan="5" data-quarto-table-cell-role="th"
data-valign="top">relation</td>
<td data-quarto-table-cell-role="th">11341185</td>
<td>POLYGON ((-4.76881 7.42618, -4.76902 7.42595, ...</td>
<td>NaN</td>
<td>yes</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>multipolygon</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">12160778</td>
<td>POLYGON ((-5.02304 6.55385, -5.02284 6.55391, ...</td>
<td>NaN</td>
<td>yes</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>multipolygon</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">12481444</td>
<td>POLYGON ((-5.01941 6.55768, -5.01938 6.55751, ...</td>
<td>NaN</td>
<td>yes</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>multipolygon</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">16542174</td>
<td>POLYGON ((-5.07582 6.584, -5.07581 6.58376, -5...</td>
<td>NaN</td>
<td>yes</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>multipolygon</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">16542175</td>
<td>POLYGON ((-5.02682 6.56471, -5.02691 6.56456, ...</td>
<td>NaN</td>
<td>yes</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>NaN</td>
<td>multipolygon</td>
</tr>
</tbody>
</table>

</div>

```python
buildings.plot(facecolor="red")
```

![](test_files/figure-markdown_strict/cell-45-output-1.png)

### **Obtenir des données de la Bank Mondiale**

Vous pouvez utiliser la class `WorldBank` de data pour cela.

```python
from cartograpy import data
wb=data.WorldBank()
```

#### **Obtenir les sources de données**

```python
wb.get_sources()
```

#### **Obtenir les indicateurs disponibles dans une source de données**

```python
# 11 Correcpond a la source Africa Development Indicators

wb.get_indicators(11)
```

#### **Obtenir la liste des pays selon une requette**

```python
wb.get_countries(query="cote")
```

    id    name
    ----  -------------
    CIV   Cote d'Ivoire

#### **Télécharger des données données d’un indicateurs**

Nous allons maintenant telecharger les données de l’indicateur
`AG.AID.NCREL.MT` qui indique le montant total, en dollars américains
courants, de l’aide publique au développement (APD) nette et de l’aide
officielle reçue par un pays au cours d’une année.

Nous utiliserons pour ce faire la méthode get_data

**`get_data(self, indicators, country='all', **kwrargs)`**

Cette méthode permet de **télécharger des données de la Banque
mondiale** pour un ou plusieurs indicateurs, et pour un ou plusieurs
pays, sur une période définie. Elle s’appuie sur le package `wbdata`
pour accéder directement aux bases de données du World Bank Group.

- **Paramètres :**

  - `indicators` : un **dictionnaire** (ou une liste) des codes
    d’indicateurs Banque mondiale à récupérer, par exemple :
    `{"AG.AID.CREL.MT": "Aide reçue nette"}` ou bien
    `["AG.AID.CREL.MT"]`.
  - `country` : code du pays (ISO alpha-3, ex. : `"CIV"` pour la
    Côte d’Ivoire) ou `"all"` pour tous les pays.
  - `**kwrargs` : autres arguments optionnels à passer à la
    fonction, par exemple :

    - `date` : période à récupérer, sous forme de tuple ou de
      string (`("2017","2020")`)
    - `freq` : fréquence des données (`"Y"` pour annuel)
    - etc.
- **Retour :**

  - Un **DataFrame pandas** contenant les valeurs des indicateurs
    demandés pour le(s) pays et la période indiqués.

```python
# Données de 2010 à 2012 pour la Côte d'Ivoire
wb.get_data({"AG.AID.CREL.MT": "Aide nette"},"CIV",date=("2010","2012"))
```

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">Aide nette</th>
</tr>
<tr>
<th data-quarto-table-cell-role="th">date</th>
<th data-quarto-table-cell-role="th"></th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">2012</td>
<td>20940.000</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2011</td>
<td>25012.995</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2010</td>
<td>12649.200</td>
</tr>
</tbody>
</table>

</div>

## **Processing de données**

`processing` vous permet d’executer des taches courantes effectuées sur
des données vectorielles. Ce modules comportes plusieurs fonctions pour
le chargement, le traitement et la sauvegarde de données vectorielles.

<figure class=''>

`<img src="test_files\figure-markdown_strict\mermaid-figure-3.png" style="width:12.95in;height:2.81in" />`

</figure>

```python
# Importation
from cartograpy.processing import *
```

### **Charger des données**

`load(filepath)`

Cette fonction permet de **charger un fichier de données vectorielles**
(shapefile, GeoJSON, GPKG, KML, GPX, CSV, parquet, etc.), quel que soit
son format. Elle détecte l’extension du fichier et utilise la méthode
adaptée pour lire le fichier sous forme de `GeoDataFrame` (pour les
formats géospatiaux) ou de `DataFrame` classique (pour CSV/parquet).**Paramètre** :

- `filepath` (str) : chemin du fichier à charger.

```python
# Chargement de données volumineuses
hexagon_data=load("data\other\hexagon 0.2_Jointure data raster.geojson")
hexagon_data.head()
```

    <>:2: SyntaxWarning: invalid escape sequence '\o'
    <>:2: SyntaxWarning: invalid escape sequence '\o'
    C:\Users\kanic\AppData\Local\Temp\ipykernel_43696\3455646038.py:2: SyntaxWarning: invalid escape sequence '\o'
      hexagon_data=load("data\other\hexagon 0.2_Jointure data raster.geojson")
    c:\Users\kanic\.virtualenvs\carto\Lib\site-packages\pyogrio\raw.py:198: RuntimeWarning: Several features with id = 1 have been found. Altering it to be unique. This warning will not be emitted anymore for this layer
      return ogr_read(

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">id</th>
<th data-quarto-table-cell-role="th">left</th>
<th data-quarto-table-cell-role="th">top</th>
<th data-quarto-table-cell-role="th">right</th>
<th data-quarto-table-cell-role="th">bottom</th>
<th data-quarto-table-cell-role="th">row_index</th>
<th data-quarto-table-cell-role="th">col_index</th>
<th data-quarto-table-cell-role="th">DN</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>1</td>
<td>-4.297638</td>
<td>9.616031</td>
<td>-4.274544</td>
<td>9.596031</td>
<td>0</td>
<td>0</td>
<td>242.0</td>
<td>POLYGON ((-4.29764 9.60603, -4.29186 9.61603, ...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>1</td>
<td>-4.297638</td>
<td>9.616031</td>
<td>-4.274544</td>
<td>9.596031</td>
<td>0</td>
<td>0</td>
<td>241.0</td>
<td>POLYGON ((-4.29764 9.60603, -4.29186 9.61603, ...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>1</td>
<td>-4.297638</td>
<td>9.616031</td>
<td>-4.274544</td>
<td>9.596031</td>
<td>0</td>
<td>0</td>
<td>244.0</td>
<td>POLYGON ((-4.29764 9.60603, -4.29186 9.61603, ...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>1</td>
<td>-4.297638</td>
<td>9.616031</td>
<td>-4.274544</td>
<td>9.596031</td>
<td>0</td>
<td>0</td>
<td>231.0</td>
<td>POLYGON ((-4.29764 9.60603, -4.29186 9.61603, ...</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>1</td>
<td>-4.297638</td>
<td>9.616031</td>
<td>-4.274544</td>
<td>9.596031</td>
<td>0</td>
<td>0</td>
<td>225.0</td>
<td>POLYGON ((-4.29764 9.60603, -4.29186 9.61603, ...</td>
</tr>
</tbody>
</table>

</div>

```python
# Chargement de mutipolygone
path="data\other\Département de Bouna.geojson"
donnee_bouna=load(path)
donnee_bouna.head()
```

    <>:2: SyntaxWarning: invalid escape sequence '\o'
    <>:2: SyntaxWarning: invalid escape sequence '\o'
    C:\Users\kanic\AppData\Local\Temp\ipykernel_43696\116216181.py:2: SyntaxWarning: invalid escape sequence '\o'
      path="data\other\Département de Bouna.geojson"

<div>


<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr style="text-align: right;">
<th data-quarto-table-cell-role="th"></th>
<th data-quarto-table-cell-role="th">id</th>
<th data-quarto-table-cell-role="th">Name</th>
<th data-quarto-table-cell-role="th">description</th>
<th data-quarto-table-cell-role="th">timestamp</th>
<th data-quarto-table-cell-role="th">begin</th>
<th data-quarto-table-cell-role="th">end</th>
<th data-quarto-table-cell-role="th">altitudeMode</th>
<th data-quarto-table-cell-role="th">tessellate</th>
<th data-quarto-table-cell-role="th">extrude</th>
<th data-quarto-table-cell-role="th">visibility</th>
<th data-quarto-table-cell-role="th">drawOrder</th>
<th data-quarto-table-cell-role="th">icon</th>
<th data-quarto-table-cell-role="th">snippet</th>
<th data-quarto-table-cell-role="th">geometry</th>
</tr>
</thead>
<tbody>
<tr>
<td data-quarto-table-cell-role="th">0</td>
<td>ID_00022</td>
<td>Bouna</td>
<td><html xmlns:fo="http://www.w3.org/1999/XSL/For...</td>
<td>None</td>
<td>None</td>
<td>None</td>
<td>clampToGround</td>
<td>-1</td>
<td>0</td>
<td>-1</td>
<td>None</td>
<td>None</td>
<td></td>
<td>MULTIPOLYGON Z (((-4.19952 9.61499 0, -4.209 9...</td>
</tr>
</tbody>
</table>
