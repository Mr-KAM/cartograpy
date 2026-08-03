from __future__ import annotations

from typing import TYPE_CHECKING, Union, List, Optional, Tuple
import os
from pathlib import Path
import datetime
from ._types import BBox
from ._optional import _require_ee, _require_geemap
if TYPE_CHECKING:
    import ee
    import geemap
import logging

logger = logging.getLogger(__name__)


class Gee:
    """
    Interface haut niveau pour Google Earth Engine.
 
    Exemple rapide
    --------------
    >>> gee = Gee()
    >>> bbox = [2.2, 48.8, 2.5, 49.0]           # Paris
    >>> s2  = gee.get_sentinel2(bbox, "2024-05-01", "2024-06-01")
    >>> gee.download(s2, bbox, filename="paris_s2.tif")
    """
 
    # ------------------------------------------------------------------ #
    # Constantes de configuration                                        #
    # ------------------------------------------------------------------ #
 
    SENTINEL2_COLLECTION   = "COPERNICUS/S2_SR_HARMONIZED"
    LANDSAT9_COLLECTION    = "LANDSAT/LC09/C02/T1_L2"
    MODIS_NDVI_COLLECTION  = "MODIS/061/MOD13A2"
    SENTINEL1_COLLECTION   = "COPERNICUS/S1_GRD"
 
    # Bandes RGB + NIR par défaut
    S2_BANDS    = ["B2", "B3", "B4", "B8"]          # Blue, Green, Red, NIR
    S2_VIS      = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
 
    L9_BANDS    = ["SR_B2", "SR_B3", "SR_B4", "SR_B5"]  # Blue, Green, Red, NIR
    L9_VIS      = {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 30000}
 
    # ------------------------------------------------------------------ #
    # Constructeur                                                       #
    # ------------------------------------------------------------------ #
 
    def __init__(self, project: Optional[str] = None, service_account: Optional[str] = None,
                 key_file: Optional[str] = None):
        """
        Initialise la connexion à Earth Engine.
 
        Parameters
        ----------
        project : str, optional
            ID du projet GCP (ex. "my-gee-project").
            Peut aussi être fourni via la variable d'environnement GEE_PROJECT.
        service_account : str, optional
            Adresse e-mail du compte de service (authentification non-interactive).
        key_file : str, optional
            Chemin vers le fichier JSON de clé du compte de service.
        """
        self._ee = _require_ee()
        self._geemap = _require_geemap()
        self.project = project or os.environ.get("GEE_PROJECT")
        self._map = None   # carte lazy-init
        self._last_collection = None
 
        self._authenticate(service_account, key_file)
 
    # ------------------------------------------------------------------ #
    # Authentification                                                   #
    # ------------------------------------------------------------------ #
 
    def _authenticate(self, service_account: Optional[str], key_file: Optional[str]) -> None:
        """Authentifie et initialise Earth Engine."""
        ee = self._ee
        try:
            if service_account and key_file:
                credentials = ee.ServiceAccountCredentials(service_account, key_file)
                ee.Initialize(credentials=credentials, project=self.project)
            else:
                ee.Initialize(project=self.project)
            logger.info("✅ Google Earth Engine initialisé avec succès.")
        except ee.EEException:
            logger.info("⚠️  Authentification requise. Lancement de ee.Authenticate()…")
            ee.Authenticate()
            ee.Initialize(project=self.project)
            logger.info("✅ Google Earth Engine initialisé avec succès.")
 
    # ------------------------------------------------------------------ #
    # Utilitaires géométrie                                              #
    # ------------------------------------------------------------------ #
 
    @staticmethod
    def bbox_to_geometry(bbox: BBox) -> ee.Geometry.Rectangle:
        """Convertit une bbox [xmin, ymin, xmax, ymax] en ee.Geometry."""
        ee = _require_ee()
        xmin, ymin, xmax, ymax = bbox
        return ee.Geometry.Rectangle([xmin, ymin, xmax, ymax])
 
    # ------------------------------------------------------------------ #
    # Masques nuageux                                                    #
    # ------------------------------------------------------------------ #
 
    @staticmethod
    def _mask_s2_clouds(image: ee.Image) -> ee.Image:
        """Masque les nuages Sentinel-2 via la bande QA60."""
        qa = image.select("QA60")
        cloud_bit_mask   = 1 << 10
        cirrus_bit_mask  = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
               qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask).divide(10000)
 
    @staticmethod
    def _mask_l9_clouds(image: ee.Image) -> ee.Image:
        """Masque les nuages Landsat-9 via la bande QA_PIXEL."""
        qa = image.select("QA_PIXEL")
        dilated  = 1 << 1
        clouds   = 1 << 3
        shadows  = 1 << 4
        mask = (qa.bitwiseAnd(dilated).eq(0)
                  .And(qa.bitwiseAnd(clouds).eq(0))
                  .And(qa.bitwiseAnd(shadows).eq(0)))
        # Facteur de réflectance Landsat C2 L2
        optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
        return image.addBands(optical, overwrite=True).updateMask(mask)
 
    # ------------------------------------------------------------------ #
    # Sentinel-2                                                         #
    # ------------------------------------------------------------------ #
 
    def get_sentinel2(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        cloud: float = 0.2,
        bands: Optional[list[str]] = None,
    ) -> ee.Image | ee.ImageCollection:
        """
        Récupère des images Sentinel-2 SR harmonisées.
 
        Parameters
        ----------
        bbox  : [xmin, ymin, xmax, ymax]
        start : date de début, format "YYYY-MM-DD"
        end   : date de fin,   format "YYYY-MM-DD"
        mosaic: si True, retourne une mosaïque mediane (ee.Image)
        clip  : si True, découpe sur la bbox
        cloud : filtre sur CLOUDY_PIXEL_PERCENTAGE (fraction, ex. 0.2 = 20 %)
        bands : liste de bandes à sélectionner (défaut : S2_BANDS)
 
        Returns
        -------
        ee.Image si mosaic=True, sinon ee.ImageCollection
        """
        ee = self._ee
        geom  = self.bbox_to_geometry(bbox)
        bands = bands or self.S2_BANDS
 
        col = (ee.ImageCollection(self.SENTINEL2_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud * 100))
               .map(self._mask_s2_clouds)
               .select(bands))
 
        self._last_collection = col
        size = col.size().getInfo()
        logger.info(f"📡 Sentinel-2 : {size} image(s) trouvée(s) [{start} → {end}]")
 
        if mosaic:
            result = col.median()
            if clip:
                result = result.clip(geom)
            return result
 
        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col
    
    # ------------------------------------------------------------------ #
    # Landsat-9                                                          #
    # ------------------------------------------------------------------ #
 
    def get_landsat9(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        cloud: float = 0.2,
        bands: Optional[list[str]] = None,
    ) -> ee.Image | ee.ImageCollection:
        """
        Récupère des images Landsat-9 Collection 2 Tier 1 L2.
 
        Parameters
        ----------
        Identiques à get_sentinel2.
        cloud : filtre sur CLOUD_COVER (fraction)
        """
        ee = self._ee
        geom  = self.bbox_to_geometry(bbox)
        bands = bands or self.L9_BANDS
 
        col = (ee.ImageCollection(self.LANDSAT9_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.lt("CLOUD_COVER", cloud * 100))
               .map(self._mask_l9_clouds)
               .select(bands))
 
        self._last_collection = col
        size = col.size().getInfo()
        logger.info(f"🛰️  Landsat-9 : {size} image(s) trouvée(s) [{start} → {end}]")
 
        if mosaic:
            result = col.median()
            if clip:
                result = result.clip(geom)
            return result
 
        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col
 
    # ------------------------------------------------------------------ #
    # Sentinel-1 SAR                                                     #
    # ------------------------------------------------------------------ #
 
    def get_sentinel1(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        polarization: str = "VV",
        pass_direction: str = "DESCENDING",
    ) -> ee.Image | ee.ImageCollection:
        """
        Récupère des images SAR Sentinel-1 GRD.
 
        Parameters
        ----------
        polarization    : "VV", "VH" ou les deux ["VV","VH"]
        pass_direction  : "ASCENDING" | "DESCENDING"
        """
        ee = self._ee
        geom = self.bbox_to_geometry(bbox)
        bands = [polarization] if isinstance(polarization, str) else polarization
 
        col = (ee.ImageCollection(self.SENTINEL1_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.eq("instrumentMode", "IW"))
               .filter(ee.Filter.eq("orbitProperties_pass", pass_direction))
               .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
               .select(bands))
 
        self._last_collection = col
        size = col.size().getInfo()
        logger.info(f"📻 Sentinel-1 : {size} image(s) trouvée(s) [{start} → {end}]")
 
        if mosaic:
            result = col.mean()
            if clip:
                result = result.clip(geom)
            return result
 
        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col
 
    # ------------------------------------------------------------------ #
    # NDVI                                                               #
    # ------------------------------------------------------------------ #
 
    def compute_ndvi(self, image: ee.Image, nir_band: str = "B8",
                     red_band: str = "B4", name: str = "NDVI") -> ee.Image:
        """Calcule et ajoute une bande NDVI à l'image."""
        ndvi = image.normalizedDifference([nir_band, red_band]).rename(name)
        return image.addBands(ndvi)
 
    def compute_ndvi_l9(self, image: ee.Image, name: str = "NDVI") -> ee.Image:
        """NDVI pour Landsat-9 (NIR=SR_B5, Red=SR_B4)."""
        return self.compute_ndvi(image, nir_band="SR_B5", red_band="SR_B4", name=name)
 
    # ------------------------------------------------------------------ #
    # Inspection de collection                                           #
    # ------------------------------------------------------------------ #
 
    def collection(
        self,
        collection_id: str,
        bbox: Optional[BBox] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> ee.ImageCollection:
        """
        Accède à n'importe quelle collection GEE avec des filtres optionnels.
 
        Parameters
        ----------
        collection_id : identifiant GEE (ex. "COPERNICUS/S2_SR_HARMONIZED")
        bbox          : filtre spatial optionnel
        start, end    : filtre temporel optionnel ("YYYY-MM-DD")
        properties    : dict {propriété: valeur} pour des filtres supplémentaires
 
        Returns
        -------
        ee.ImageCollection filtrée
        """
        ee = self._ee
        col = ee.ImageCollection(collection_id)
 
        if bbox is not None:
            col = col.filterBounds(self.bbox_to_geometry(bbox))
        if start and end:
            col = col.filterDate(start, end)
        if properties:
            for prop, value in properties.items():
                col = col.filter(ee.Filter.eq(prop, value))
 
        self._last_collection = col
        size = col.size().getInfo()
        logger.info(f"📂 Collection «{collection_id}» : {size} image(s)")
        return col
 
    def info(self, data: Union[ee.Image, ee.ImageCollection]) -> dict:
        """Retourne les métadonnées (dict) d'une image ou collection."""
        return data.getInfo()
 
    def count(self, col: Optional[ee.ImageCollection] = None) -> int:
        """Nombre d'images dans une collection (dernière par défaut)."""
        col = col or self._last_collection
        if col is None:
            raise ValueError("Aucune collection disponible.")
        return col.size().getInfo()
 
    def dates(self, col: Optional[ee.ImageCollection] = None) -> list[str]:
        """Liste des dates d'acquisition d'une collection."""
        col = col or self._last_collection
        if col is None:
            raise ValueError("Aucune collection disponible.")
        dates = col.aggregate_array("system:time_start").getInfo()
        import datetime
        return [
            datetime.datetime.utcfromtimestamp(d / 1000).strftime("%Y-%m-%d")
            for d in dates
        ]
 
    # ------------------------------------------------------------------ #
    # Export / Téléchargement                                            #
    # ------------------------------------------------------------------ #
 
    def download(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        filename: str = "image.tif",
        scale: int = 10,
        crs: str = "EPSG:4326",
        bands: Optional[list[str]] = None,
        output_dir: str = ".",
        mosaic_col: bool = True,
    ) -> Path:
        """
        Télécharge une ee.Image (ou ee.ImageCollection) localement via geemap.
 
        Parameters
        ----------
        data        : image ou collection à télécharger
        bbox        : zone d'export [xmin, ymin, xmax, ymax] (obligatoire si image non clippée)
        filename    : nom du fichier de sortie (.tif)
        scale       : résolution en mètres (10 m pour S2, 30 m pour L9)
        crs         : système de coordonnées de sortie
        bands       : sous-ensemble de bandes à exporter
        output_dir  : dossier de destination
        mosaic_col  : si data est une collection, faire une médiane avant export
 
        Returns
        -------
        Path vers le fichier téléchargé
        """
        ee = self._ee
        geemap = self._geemap
        # Résolution d'une éventuelle collection
        if isinstance(data, ee.ImageCollection):
            logger.info("ℹ️  Collection détectée → médiane appliquée avant export.")
            data = data.median() if mosaic_col else data.mosaic()
 
        # Sélection de bandes
        if bands:
            data = data.select(bands)
 
        # Région d'export
        region = None
        if bbox is not None:
            region = self.bbox_to_geometry(bbox)
 
        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
 
        logger.info(f"⬇️  Téléchargement vers «{output_path}» (scale={scale}m, crs={crs})…")
        geemap.ee_export_image(
            data,
            filename=str(output_path),
            scale=scale,
            region=region,
            crs=crs,
            file_per_band=False,
        )
        logger.info(f"✅ Fichier sauvegardé : {output_path}")
        return output_path
 
    def export_to_drive(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        description: str = "gee_export",
        folder: str = "GEE_exports",
        scale: int = 10,
        crs: str = "EPSG:4326",
        max_pixels: int = int(1e13),
    ) -> None:
        """
        Lance une tâche d'export vers Google Drive (asynchrone).
 
        Parameters
        ----------
        description : nom de la tâche et du fichier dans Drive
        folder      : dossier Drive de destination
        """
        ee = self._ee
        if isinstance(data, ee.ImageCollection):
            data = data.median()
 
        region = self.bbox_to_geometry(bbox) if bbox else None
 
        task = ee.batch.Export.image.toDrive(
            image=data,
            description=description,
            folder=folder,
            scale=scale,
            region=region,
            crs=crs,
            maxPixels=max_pixels,
        )
        task.start()
        logger.info(f"🚀 Tâche Drive lancée : «{description}» → dossier «{folder}»")
        logger.info("   Suivre avec : ee.batch.Task.list()")
 
    # ------------------------------------------------------------------ #
    # Visualisation                                                      #
    # ------------------------------------------------------------------ #
 
    def map(self, center: Optional[list[float]] = None, zoom: int = 8) -> geemap.Map:
        """
        Retourne (ou crée) une carte geemap interactive.
 
        Parameters
        ----------
        center : [lat, lon] du centre de la carte
        zoom   : niveau de zoom initial
        """
        geemap = self._geemap
        if self._map is None:
            self._map = geemap.Map()
        if center:
            self._map.setCenter(center[1], center[0], zoom)
        return self._map
 
    def add_layer(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        vis_params: Optional[dict] = None,
        name: str = "Layer",
        bbox: Optional[BBox] = None,
    ) -> geemap.Map:
        """
        Ajoute une image (ou collection) à la carte interactive.
 
        Parameters
        ----------
        vis_params : dict de visualisation GEE (bands, min, max, palette…)
        name       : nom du layer dans la carte
        bbox       : si fourni, centre la carte sur la bbox
        """
        ee = self._ee
        m = self.map()
 
        if isinstance(data, ee.ImageCollection):
            data = data.median()
 
        m.addLayer(data, vis_params or {}, name)
 
        if bbox is not None:
            xmin, ymin, xmax, ymax = bbox
            m.centerObject(self.bbox_to_geometry(bbox))
 
        logger.info(f"🗺️  Layer «{name}» ajouté à la carte.")
        return m
 
    def show_map(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        vis_params: Optional[dict] = None,
        name: str = "Layer",
    ) -> geemap.Map:
        """Raccourci : crée la carte, ajoute le layer et l'affiche."""
        return self.add_layer(data, vis_params=vis_params, name=name, bbox=bbox)
 
    # ------------------------------------------------------------------ #
    # Statistiques zonales                                               #
    # ------------------------------------------------------------------ #
 
    def zonal_stats(
        self,
        image: ee.Image,
        bbox: BBox,
        scale: int = 30,
        reducer: str = "mean",
    ) -> dict:
        """
        Calcule des statistiques zonales sur une bbox.
 
        Parameters
        ----------
        reducer : "mean" | "median" | "min" | "max" | "sum"
 
        Returns
        -------
        dict {band: valeur}
        """
        ee = self._ee
        reducers = {
            "mean":   ee.Reducer.mean(),
            "median": ee.Reducer.median(),
            "min":    ee.Reducer.min(),
            "max":    ee.Reducer.max(),
            "sum":    ee.Reducer.sum(),
        }
        r = reducers.get(reducer, ee.Reducer.mean())
        geom = self.bbox_to_geometry(bbox)
        stats = image.reduceRegion(reducer=r, geometry=geom, scale=scale, maxPixels=int(1e10))
        return stats.getInfo()
 
    # ------------------------------------------------------------------ #
    # Représentation textuelle                                             #
    # ------------------------------------------------------------------ #
 
    def __repr__(self) -> str:
        project_str = f"project={self.project!r}" if self.project else "project=default"
        return f"Gee({project_str})"
