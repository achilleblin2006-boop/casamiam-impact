"""
Graphiques du projet (PNG dans outputs/figures). Aucun nom de producteur n'y apparaît.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config

VERT, GRIS = "#2E4A4C", "#B8C4C4"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def _sauver(fig, nom):
    fig.tight_layout()
    fig.savefig(config.DOSSIER_FIGURES / nom, dpi=200)
    plt.close(fig)


def croissance_plateforme(plateforme):
    p = plateforme[plateforme.mois <= config.FIN_PERIODE]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(p.mois, p.commandes, width=25, color=VERT)
    ax.set_title("Commandes mensuelles sur Casamiam")
    ax.set_ylabel("Commandes")
    _sauver(fig, "01_croissance_plateforme.png")


def produits_et_activation(tab):
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    barres = ax.bar(tab.index.astype(str), tab.taux_activation * 100, color=VERT)
    ax.bar_label(barres, labels=[f"{v:.0%}" for v in tab.taux_activation], padding=3)
    ax.set_xlabel("Nombre de produits visibles en boutique")
    ax.set_ylabel("Boutiques ayant vendu (%)")
    ax.set_title("Plus de produits en ligne, plus de boutiques qui vendent")
    ax.set_ylim(0, 100)
    _sauver(fig, "02_produits_activation.png")


def concentration(base):
    ca = base[base.inclus_analyse & base.active_12m].ca_12m.sort_values(ascending=False).reset_index(drop=True)
    cumul = ca.cumsum() / ca.sum() * 100
    part_boutiques = (cumul.index + 1) / len(ca) * 100
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.plot(part_boutiques, cumul, color=VERT, lw=2)
    ax.plot([0, 100], [0, 100], color=GRIS, ls="--", lw=1)
    ax.set_xlabel("% des boutiques actives (des plus grosses aux plus petites)")
    ax.set_ylabel("% cumulé du CA")
    ax.set_title("Concentration du chiffre d'affaires")
    _sauver(fig, "03_concentration_ca.png")


def etat_activite(base):
    pop = base[base.inclus_analyse]
    comptes = pop.etat_activite.value_counts().reindex(["Active", "Dormante", "Jamais vendu"])
    fig, ax = plt.subplots(figsize=(6, 3.2))
    barres = ax.barh(comptes.index, comptes.values, color=[VERT, "#7A9A9C", GRIS])
    ax.bar_label(barres, padding=3)
    ax.invert_yaxis()
    ax.set_title("État d'activité des boutiques au 1er octobre 2026")
    _sauver(fig, "04_etat_activite.png")


def familles(base):
    pop = base[base.inclus_analyse & base.active_12m & base.famille_principale.notna()]
    parts = (pop.groupby("famille_principale").ca_12m.sum() / pop.ca_12m.sum()).sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    barres = ax.barh(parts.index, parts.values * 100, color=VERT)
    ax.bar_label(barres, labels=[f"{v:.0%}" for v in parts.values], padding=3)
    ax.set_xlabel("Part du CA sur 12 mois (%)")
    ax.set_title("Répartition du CA par famille de produits")
    _sauver(fig, "05_familles.png")


def distances(points):
    d = points.distance_km.dropna()
    tranches = pd.cut(d, [-0.01, 1, 10, 50, 10**4], labels=["< 1 km\n(sur place)", "1-10 km", "10-50 km", "> 50 km"])
    parts = tranches.value_counts(normalize=True).sort_index()
    fig, ax = plt.subplots(figsize=(6, 3.4))
    barres = ax.bar(parts.index.astype(str), parts.values * 100, color=VERT)
    ax.bar_label(barres, labels=[f"{v:.0%}" for v in parts.values], padding=3)
    ax.set_ylabel("% des points de retrait")
    ax.set_title("Distance entre le producteur et ses points de retrait")
    ax.set_ylim(0, 105)
    _sauver(fig, "06_distances_retrait.png")


def tout_produire(base, points, plateforme, tab_produits):
    config.DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
    croissance_plateforme(plateforme)
    produits_et_activation(tab_produits)
    concentration(base)
    etat_activite(base)
    familles(base)
    distances(points)
