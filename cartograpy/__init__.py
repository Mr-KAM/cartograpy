# from .countries_iso3 import *
# from .iso3_codes import *
from .iso_code import *
# from .boundaries import *

from .data import *
from .processing import *
from .mapper import *
from .styling import *
from .geocoder import *
from .converter import *
from .mapper2 import *

import os

def init_project(path=None):
    """
    Initialise un projet cartograpy en créant les dossiers 'data' et 'output'.

    Args:
        path: Chemin du répertoire où créer les dossiers.
              Si None, utilise le répertoire courant.

    Returns:
        str: Chemin du projet initialisé.
    """
    if path is None:
        path = os.getcwd()

    data_dir = os.path.join(path, "data")
    output_dir = os.path.join(path, "output")

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    print(f"✅ Projet initialisé dans : {os.path.abspath(path)}")
    print(f"   📁 {data_dir}")
    print(f"   📁 {output_dir}")

    return os.path.abspath(path)


