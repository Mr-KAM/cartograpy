
<div align="center">
  <img src="data/logo.png" alt="Logo" width="200">
	<p>Mapping in Python, the way it was always meant to be.</p>
</div>

# **PRESENTATION**

Cartograpy est un package python qui permet de manipuler des données
geographiques et de creer des cartes simplement avec python.

![img](https://file+.vscode-resource.vscode-cdn.net/c%3A/Users/kanic/OneDrive/Formations/Cartographie%20avec%20python/cartograpy/data/create_python_maps.py%20(17).png "Mapiing with cartograpy")

# **FONCTIONNALITE**

- Telecharger des données de découpage administratif de pays
- Importer des données de types vectorielles et matricielles
- Faire des traitement sur les données geospatiales importé
- Creer des cartes et les personnaliser simplement

# **INSTALLATION**

Pour installer le package cartograpy, vous pouvez utiliser pip. Ouvrez
votre terminal ou invite de commande et exécutez la commande suivante :

```bash
pip install cartograpy
```

# **UTILISATION**

## **Obtension de données géographiques**

### *Récupérer les limites administratives d’un ou plusieurs pays*

```python
# Importation
from cartograpy import data
client = data.GeoBoundaries()
```

**Les niveau de subbdivision administrative disponibles sont :**

Il existe 5 subdivisions administratives disponibles :

```python
print(client.adminLevels())
```

| Niveau GeoBoundaries | Nom commun (FR)            | Nom commun (EN)       |
| -------------------- | -------------------------- | --------------------- |
| ADM0                 | Pays                       | Country               |
| ADM1                 | Région / État / Province | State / Region        |
| ADM2                 | Département / District    | District / County     |
| ADM3                 | Sous-préfecture / Commune | Subdistrict / Commune |
| ADM4                 | Village / Localité        | Village / Locality    |
| ADM5                 | Quartier / Secteur         | Neighborhood / Sector |

**Remarques importantes :**

- Le nombre de niveaux dépend du pays. Certains pays s’arrêtent à
  ADM2, d’autres vont jusqu’à ADM4 ou ADM5.
- Le nom réel des subdivisions varie d’un pays à l’autre (ex :
  “State”, “Region”, “Province”, “Department”, etc.).
- GeoBoundaries propose toujours au moins le niveau ADM0 (frontière
  nationale).

Pour savoir si un niveau administratif est disponible pour un pays, vous
pouvez utiliser la méthode `is_valid_adm` de l’objet `GeoBoundaries`.
Voici un exemple :

```python
print(client.is_valid_adm("CIV","ADM1"))  # Exemple pour vérifier si le niveau ADM1 est valide pour la Côte d'Ivoire
# Ou encore
print(client._get_smallest_adm("CIV"))  # Exemple pour vérifier si le niveau admin minimum pour la Côte d'Ivoire
```

    True
    Smallest ADM level found for CIV : ADM3
    ADM3

**Les codes des pays sont conformes à la norme ISO 3166-1 alpha-3 :**

Pour obtenir la liste des pays valides, vous pouvez utiliser la méthode
`countries()` de l’objet `GeoBoundaries`. Voici un exemple :

```python
client.countries()[0:10]  # Affiche les 10 premiers pays
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

```python
client.get_iso3("burk")
```

    'BFA'

```python
client.get_iso3("con")  # Exemple pour obtenir le code ISO d'un pays
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

```python

# Exemple 1: Récupérer les données administratives des régions de la cote d'ivoire
civ_data = client.adm("CIV", "ADM2")
civ_data.head()
```

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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
# Exemple 2 : Récupérer les limites administratives de plusieurs pays (senegal et mali ici)
countries_data = client.adm(["SEN", "mali"], "ADM2")
countries_data["mali"].head()
```

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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

### Récupérer les métadonnées d’un territoire

```python

# Récupérer les métadonnées d'un territoire
metadata_civ = client.metadata("CIV", "ADM0")


print(f"Métadonnées disponibles pour la Côte d'Ivoire: {metadata_civ.keys()}")
```

    Métadonnées disponibles pour la Côte d'Ivoire: dict_keys(['boundaryID', 'boundaryName', 'boundaryISO', 'boundaryYearRepresented', 'boundaryType', 'boundaryCanonical', 'boundarySource', 'boundaryLicense', 'licenseDetail', 'licenseSource', 'boundarySourceURL', 'sourceDataUpdateDate', 'buildDate', 'Continent', 'UNSDG-region', 'UNSDG-subregion', 'worldBankIncomeGroup', 'admUnitCount', 'meanVertices', 'minVertices', 'maxVertices', 'meanPerimeterLengthKM', 'minPerimeterLengthKM', 'maxPerimeterLengthKM', 'meanAreaSqKM', 'minAreaSqKM', 'maxAreaSqKM', 'staticDownloadLink', 'gjDownloadURL', 'tjDownloadURL', 'imagePreview', 'simplifiedGeometryGeoJSON'])

```python
metadata_civ["Continent"]
```

    'Africa'

```python
metadata_civ["UNSDG-subregion"]
```

    'Western Africa'

```python
metadata_civ["UNSDG-region"]
```

    'Sub-Saharan Africa'

```python
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

### *Géocoder une ou plusieurs adresses*

Le geocodage permet de convertir des adresses en coordonnées
géographiques (latitude et longitude). Vous pouvez géocoder une ou
plusieurs adresses en utilisant les méthode `geocode` et `geocode_batch`
de l’objet `Geocoder`.

```python
from cartograpy import data
geocoder= data.Geocoder()
```

**Géocoder une adresse**

```python
address = "bouaké"
result = geocoder.geocode(address)

# Adresse trouvée
result[0]
```

    Début du géocodage de 1 localité(s)...
    Géocodage terminé.

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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
<td>{'place_id': 277285966, 'licence': 'Data © Ope...</td>
<td>POINT (-5.02836 7.68902)</td>
</tr>
</tbody>
</table>

</div>

```python
# Adresse non trouvée
result[1]
```

    []

**Geocoder une liste d’adresses**

```python
liste_adresses = ["Abidjan", "Yamoussoukro", "Bouaké", "Korhogo","Man CI", "","portbouet"]
results=geocoder.geocode(liste_adresses)

# Adresses trouvées
results[0]
```

    Début du géocodage de 7 localité(s)...
    Géocodage terminé.

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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
<td>Abidjan, Le Plateau, Abidjan, Côte d’Ivoire</td>
<td>5.320357</td>
<td>-4.016107</td>
<td>0.0</td>
<td>{'place_id': 277113208, 'licence': 'Data © Ope...</td>
<td>POINT (-4.01611 5.32036)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">1</td>
<td>Yamoussoukro</td>
<td>Yamoussoukro, Côte d’Ivoire</td>
<td>6.820007</td>
<td>-5.277603</td>
<td>0.0</td>
<td>{'place_id': 405157296, 'licence': 'Data © Ope...</td>
<td>POINT (-5.2776 6.82001)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">2</td>
<td>Bouaké</td>
<td>Bouaké, Gbêkê, Vallée du Bandama, Côte d’Ivoire</td>
<td>7.689021</td>
<td>-5.028355</td>
<td>0.0</td>
<td>{'place_id': 277285966, 'licence': 'Data © Ope...</td>
<td>POINT (-5.02836 7.68902)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">3</td>
<td>Korhogo</td>
<td>Korhogo, Poro, Savanes, Côte d’Ivoire</td>
<td>9.458070</td>
<td>-5.631629</td>
<td>0.0</td>
<td>{'place_id': 277168989, 'licence': 'Data © Ope...</td>
<td>POINT (-5.63163 9.45807)</td>
</tr>
<tr>
<td data-quarto-table-cell-role="th">4</td>
<td>Man CI</td>
<td>Man, Tonkpi, Montagnes, Côte d’Ivoire</td>
<td>7.410258</td>
<td>-7.550372</td>
<td>0.0</td>
<td>{'place_id': 276691276, 'licence': 'Data © Ope...</td>
<td>POINT (-7.55037 7.41026)</td>
</tr>
</tbody>
</table>

</div>

```python
# Adresses non trouvée
results[1]
```

    ['', 'portbouet']

## **Processing de données**

`processing` vous permet d’executer des taches courantes effectuées sur
des données vectorielles.

```python
# Importation
from cartograpy.processing  import *
```

**Charger des données**

```python
hexagon_data=load("data\other\hexagon 0.2_Jointure data raster.geojson")
hexagon_data.head()
```

    <>:1: SyntaxWarning: invalid escape sequence '\o'
    <>:1: SyntaxWarning: invalid escape sequence '\o'
    C:\Users\kanic\AppData\Local\Temp\ipykernel_65224\3617017383.py:1: SyntaxWarning: invalid escape sequence '\o'
      hexagon_data=load("data\other\hexagon 0.2_Jointure data raster.geojson")
    c:\Users\kanic\.virtualenvs\carto\Lib\site-packages\pyogrio\raw.py:198: RuntimeWarning: Several features with id = 1 have been found. Altering it to be unique. This warning will not be emitted anymore for this layer
      return ogr_read(

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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
path="data\other\Département de Bouna.geojson"
donnee_bouna=load(path)
donnee_bouna.head()
```

    <>:1: SyntaxWarning: invalid escape sequence '\o'
    <>:1: SyntaxWarning: invalid escape sequence '\o'
    C:\Users\kanic\AppData\Local\Temp\ipykernel_65224\847831339.py:1: SyntaxWarning: invalid escape sequence '\o'
      path="data\other\Département de Bouna.geojson"

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }`</style>`

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
