import marimo

__generated_with = "0.23.0"
app = marimo.App(layout_file="layouts/1-cartograpy-project.slides.json")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Initialisation
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path.cwd().parent   # car notebook est dans notebook/ et pas dans le root du projet
    sys.path.insert(0, str(PROJECT_ROOT))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Initialiser un nouveau projet SIG
    """)
    return


@app.cell
def _():
    import cartograpy.project as project

    # Initialiser un projet avec un CRS et des dossiers par défaut
    projet = project.Project(
        path="./mon_projet/",   # répertoire racine du projet
        data_dir="data",        # dossier des données
        output_dir="output",    # dossier des résultats
        crs="EPSG:4326"         # système de coordonnées (WGS 84)
    )
    projet.init()
    return (projet,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Charger des données dans le projet
    """)
    return


@app.cell
def _(projet):
    # Copier un fichier existant (nom et extension déduits)
    projet.add_data("../data/vector/gadm41_CIV.gpkg")

    # Copier avec un nom personnalisé
    projet.add_data("../data/raster/DEM.tif", filename="altitude")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Information sur le projet
    """)
    return


@app.cell
def _(projet):
    projet.infos()
    return


@app.cell
def _(projet):
    projet.list_data()
    return


@app.cell
def _(projet):
    projet.list_datasets()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
