# setup.py
from setuptools import setup, find_packages

setup(
    name="cartograpy",
    version="1.0",
    description="Packages python pour créer des cartes",
    long_description="Ce package fournit des outils pour créer des cartes en utilisant des données géographiques issus de geoboundaries. Il inclut des fonctionnalités pour télécharger des données géographiques, les traiter et les visualiser.",
    url="https://github.com/mr-kam/cartograpy",
    author="Anicet Cyrille Kambou",
    packages=find_packages(),
    install_requires=[
        "requests",
        "geopandas",
        "click"
    ],
    entry_points={
        "console_scripts": [
            "geoboundaries-cli = geoboundaries.cli:main"
        ]
    }
)
