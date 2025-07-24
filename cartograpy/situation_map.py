import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

fig = plt.figure(figsize=(10, 5))

# Grille de 2 lignes x 2 colonnes
gs = GridSpec(2, 2, width_ratios=[2, 8], height_ratios=[4, 6])

# Première colonne, première ligne (20% de la largeur, 40% de la hauteur)
ax1 = fig.add_subplot(gs[0, 0])
ax1.set_title("Col 1, Ligne 1 (20%x40%)")

# Première colonne, deuxième ligne (20% de la largeur, 60% de la hauteur)
ax2 = fig.add_subplot(gs[1, 0])
ax2.set_title("Col 1, Ligne 2 (20%x60%)")

# Deuxième colonne, occupe les deux lignes (80% de la largeur, 100% de la hauteur)
ax3 = fig.add_subplot(gs[:, 1])
ax3.set_title("Col 2 (80% hauteur totale)")

plt.tight_layout()
plt.show()
