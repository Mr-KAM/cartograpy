import gpxpy
import gpxpy.gpx
import gpxpy
import gpxpy.gpx
import geojson
from pykml import parser

class converter:
    """
    Classe pour gérer et convertir les fichiers géographiques (GPX, GeoJSON, KML).
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.tracks = []
        self.waypoints = []
        self._parse_file()

    def _parse_file(self):
        """
        Détecte et parse le fichier en fonction de son format (GPX, GeoJSON, KML).
        """
        try:
            if self.file_path.endswith('.gpx'):
                self._parse_gpx()
            elif self.file_path.endswith('.geojson'):
                self._parse_geojson()
            elif self.file_path.endswith('.kml'):
                self._parse_kml()
            else:
                raise ValueError("Format de fichier non supporté")
        except Exception as e:
            print(f"Erreur lors du traitement du fichier : {e}")

    def _parse_gpx(self):
        with open(self.file_path, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

        # Extraction des waypoints
        for waypoint in gpx.waypoints:
            self.waypoints.append({
                'name': waypoint.name,
                'latitude': waypoint.latitude,
                'longitude': waypoint.longitude,
                'elevation': waypoint.elevation
            })

        # Extraction des tracks
        for track in gpx.tracks:
            track_data = {
                'name': track.name,
                'segments': []
            }
            for segment in track.segments:
                segment_points = []
                for point in segment.points:
                    segment_points.append({
                        'latitude': point.latitude,
                        'longitude': point.longitude,
                        'elevation': point.elevation,
                        'time': point.time
                    })
                track_data['segments'].append(segment_points)
            self.tracks.append(track_data)

    def _parse_geojson(self):
        with open(self.file_path, 'r') as geojson_file:
            data = geojson.load(geojson_file)

        # Extraction des features
        for feature in data['features']:
            geometry = feature['geometry']
            if geometry['type'] == 'Point':
                self.waypoints.append({
                    'name': feature['properties'].get('name', None),
                    'latitude': geometry['coordinates'][1],
                    'longitude': geometry['coordinates'][0],
                    'elevation': feature['properties'].get('elevation', None)
                })
            elif geometry['type'] == 'LineString':
                track_data = {
                    'name': feature['properties'].get('name', None),
                    'segments': [
                        [{'latitude': coord[1], 'longitude': coord[0], 'elevation': None} for coord in geometry['coordinates']]
                    ]
                }
                self.tracks.append(track_data)

    def _parse_kml(self):
        with open(self.file_path, 'r') as kml_file:
            kml = parser.parse(kml_file).getroot()

        # Extraction des waypoints et tracks (simplifié pour démonstration)
        for placemark in kml.Document.Folder.Placemark:
            if hasattr(placemark, 'Point'):
                coordinates = placemark.Point.coordinates.text.strip().split(',')
                self.waypoints.append({
                    'name': placemark.name.text,
                    'latitude': float(coordinates[1]),
                    'longitude': float(coordinates[0]),
                    'elevation': float(coordinates[2]) if len(coordinates) > 2 else None
                })

    def to_geojson(self):
        """
        Convertit les données en GeoJSON.
        """
        features = []

        # Ajout des waypoints
        for waypoint in self.waypoints:
            features.append(geojson.Feature(
                geometry=geojson.Point((waypoint['longitude'], waypoint['latitude'])),
                properties={
                    'name': waypoint['name'],
                    'elevation': waypoint['elevation']
                }
            ))

        # Ajout des tracks
        for track in self.tracks:
            for segment in track['segments']:
                coordinates = [(point['longitude'], point['latitude']) for point in segment]
                features.append(geojson.Feature(
                    geometry=geojson.LineString(coordinates),
                    properties={
                        'name': track['name']
                    }
                ))

        return geojson.FeatureCollection(features)




def extract_gpx_data(file_path):
    """
    Extrait les tracks et les waypoints d'un fichier GPX.

    :param file_path: Chemin vers le fichier GPX
    :return: Un dictionnaire contenant les tracks et les waypoints
    """
    try:
        with open(file_path, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

        # Extraction des waypoints
        waypoints = []
        for waypoint in gpx.waypoints:
            waypoints.append({
                'name': waypoint.name,
                'latitude': waypoint.latitude,
                'longitude': waypoint.longitude,
                'elevation': waypoint.elevation
            })

        # Extraction des tracks
        tracks = []
        for track in gpx.tracks:
            track_data = {
                'name': track.name,
                'segments': []
            }
            for segment in track.segments:
                segment_points = []
                for point in segment.points:
                    segment_points.append({
                        'latitude': point.latitude,
                        'longitude': point.longitude,
                        'elevation': point.elevation,
                        'time': point.time
                    })
                track_data['segments'].append(segment_points)
            tracks.append(track_data)

        return {
            'tracks': tracks,
            'waypoints': waypoints
        }

    except Exception as e:
        print(f"Erreur lors de la lecture du fichier GPX : {e}")
        return None

# Exemple d'utilisation
if __name__ == "__main__":
    file_path = "votre_fichier.gpx"  # Remplacez par le chemin vers votre fichier GPX
    gpx_data = extract_gpx_data(file_path)

    if gpx_data:
        print("Waypoints:", gpx_data['waypoints'])
        print("Tracks:", gpx_data['tracks'])

# Exemple d'utilisation
if __name__ == "__main__":
    file_path = "votre_fichier.gpx"  # Remplacez par le chemin vers votre fichier (GPX, GeoJSON, KML)
    processor = converter(file_path)

    # Conversion en GeoJSON
    geojson_data = processor.to_geojson()
    print(geojson.dumps(geojson_data, indent=2))