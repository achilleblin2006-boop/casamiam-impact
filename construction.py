"""
Construction de la base d'analyse : une ligne par boutique, avec ses ventes,
ses produits, sa localisation, ses points de retrait et ses indicateurs.
"""
import numpy as np
import pandas as pd

import config
from chargement import distance_km, normaliser


def famille_de(categorie):
    """Rattache une catégorie Casamiam à une famille de produits (voir config.FAMILLES)."""
    nom = str(categorie).lower()
    if nom in config.CATEGORIES_GENERIQUES:
        return "Autre / générique"
    for famille, mots_cles in config.FAMILLES:
        if any(mot in nom for mot in mots_cles):
            return famille
    return "Autre / générique"


def _mois_entre(debut, fin):
    """Nombre de mois entiers entre deux dates (Series)."""
    return (fin.year - debut.dt.year) * 12 + (fin.month - debut.dt.month)


def construire_base(d):
    ventes, boutiques, adresses = d["ventes"], d["boutiques"], d["adresses"]

    # 1. Univers des boutiques : la fiche Store + les boutiques de l'ancien système,
    #    présentes uniquement dans les ventes (la fiche a été recréée en 2023).
    dernier_nom = ventes.sort_values("mois").groupby("store_id")["nom_vente"].last()
    anciennes = pd.DataFrame({"store_id": sorted(set(ventes.store_id) - set(boutiques.store_id))})
    anciennes["nom"] = anciennes.store_id.map(dernier_nom)
    anciennes["statut"] = "ancien système"
    colonnes_liens = {"facebook": "Facebook URL", "instagram": "Instagram URL", "tiktok": "Tiktok URL",
                      "google_business": "Google Business Profile URL", "linkedin": "Linkedin URL"}
    base = pd.concat([boutiques[["store_id", "nom", "statut", "date_creation", "AddressId",
                                 *colonnes_liens.values()]], anciennes], ignore_index=True)
    base["dans_fiche"] = base.store_id.isin(boutiques.store_id)
    for court, colonne in colonnes_liens.items():
        base[f"lien_{court}"] = base[colonne].notna()
    base["nb_reseaux"] = base[[f"lien_{c}" for c in colonnes_liens]].sum(axis=1)
    base = base.drop(columns=list(colonnes_liens.values()))

    # 2. Localisation
    base = base.merge(adresses[["AddressId", "ville", "code_postal", "lat", "lon"]], on="AddressId", how="left")
    base["departement"] = base.code_postal.str[:2]

    # 3. Produits et familles
    categories = d["categories"].copy()
    categories["famille"] = categories.categorie.map(famille_de)
    produits = d["produits"].merge(categories, on="CategoryId", how="left")
    visibles = produits[produits.Visible == 1]
    agg = produits.groupby("store_id").agg(nb_produits=("Nombre", "sum"))
    agg["nb_produits_visibles"] = visibles.groupby("store_id").Nombre.sum()
    # Famille principale : celle qui compte le plus de produits, en priorité parmi les produits visibles
    utiles = produits[produits.famille != "Autre / générique"].copy()
    a_des_visibles = utiles[utiles.Visible == 1].store_id.unique()
    utiles = utiles[(utiles.Visible == 1) | ~utiles.store_id.isin(a_des_visibles)]
    agg["famille_principale"] = (utiles.groupby(["store_id", "famille"]).Nombre.sum()
                                 .reset_index().sort_values("Nombre").groupby("store_id").famille.last())
    agg["nb_familles"] = utiles.groupby("store_id").famille.nunique()
    base = base.merge(agg.reset_index(), on="store_id", how="left")
    for c in ["nb_produits", "nb_produits_visibles", "nb_familles"]:
        base[c] = base[c].fillna(0).astype(int)

    # 4. Ventes : historique complet puis période de 12 mois
    histo = ventes.groupby("store_id").agg(commandes_total=("commandes", "sum"), ca_total=("ca", "sum"),
                                           premier_mois_vente=("mois", "min"), dernier_mois_vente=("mois", "max"))
    periode = ventes[ventes.mois.between(config.DEBUT_PERIODE, config.FIN_PERIODE)]
    p12 = periode.groupby("store_id").agg(commandes_12m=("commandes", "sum"), ca_12m=("ca", "sum"),
                                          acheteurs_mois_12m=("acheteurs", "sum"),
                                          mois_avec_ventes=("mois", "nunique"), ca_meilleur_mois=("ca", "max"))
    base = base.merge(histo.reset_index(), on="store_id", how="left").merge(p12.reset_index(), on="store_id", how="left")
    for c in ["commandes_total", "commandes_12m", "acheteurs_mois_12m", "mois_avec_ventes"]:
        base[c] = base[c].fillna(0).astype(int)
    for c in ["ca_total", "ca_12m"]:
        base[c] = base[c].fillna(0.0)

    # 5. Dates, ancienneté, existence sur la période
    creation_mois = base.date_creation.dt.to_period("M").dt.to_timestamp()
    base["date_debut"] = pd.concat([creation_mois, base.premier_mois_vente], axis=1).min(axis=1)
    base["anciennete_mois"] = _mois_entre(base.date_debut, config.DATE_REFERENCE)
    debut_effectif = base.date_debut.clip(lower=config.DEBUT_PERIODE)
    base["mois_existence_12m"] = (_mois_entre(debut_effectif, config.FIN_PERIODE) + 1).clip(0, 12).fillna(0).astype(int)
    base["phase"] = np.where(base.anciennete_mois < 6, "Néo-entrant (<6 mois)", "Installé")

    # 6. Indicateurs de performance
    existe = base.mois_existence_12m > 0
    base["active_12m"] = base.commandes_12m > 0
    base["ca_mensuel"] = (base.ca_12m / base.mois_existence_12m).where(existe)
    base["panier_moyen"] = (base.ca_12m / base.commandes_12m).where(base.commandes_12m > 0)
    base["part_meilleur_mois"] = (base.ca_meilleur_mois / base.ca_12m).where(base.ca_12m > 0)
    evaluable = (base.commandes_12m >= 10) & (base.mois_existence_12m >= 3)
    base["vente_par_campagnes"] = np.where(evaluable, np.where(base.part_meilleur_mois >= config.SEUIL_CAMPAGNE, "Oui", "Non"), "Non évaluable")
    base["mois_depuis_vente"] = _mois_entre(base.dernier_mois_vente, config.DATE_REFERENCE)
    base["etat_activite"] = np.select(
        [base.commandes_total.eq(0), base.mois_depuis_vente > config.SEUIL_DORMANCE_MOIS],
        ["Jamais vendu", "Dormante"], "Active")
    base["tranche_produits"] = pd.cut(base.nb_produits_visibles, [-1, 0, 5, 15, 30, 10**6],
                                      labels=["0", "1-5", "6-15", "16-30", "31+"])

    # 7. Points de retrait et distances au producteur
    points = (d["points"].merge(adresses[["AddressId", "lat", "lon"]].rename(columns={"lat": "plat", "lon": "plon"}),
                                on="AddressId", how="left")
              .merge(base[["store_id", "lat", "lon"]], on="store_id", how="left"))
    points["distance_km"] = distance_km(points.lat, points.lon, points.plat, points.plon)
    dist = points.groupby("store_id").agg(nb_points_retrait=("point_id", "size"), distance_moy_km=("distance_km", "mean"))
    base = base.merge(dist.reset_index(), on="store_id", how="left")
    base["nb_points_retrait"] = base.nb_points_retrait.fillna(0).astype(int)

    # 8. Population analysée : hors tests, boutiques existant sur la période
    base["suspect_test"] = base.nom.isna() | base.nom.map(normaliser).fillna("").str.contains(config.MOTIF_TEST)
    base["inclus_analyse"] = ~base.suspect_test & existe

    return base, points, categories


def anonymiser(base):
    """Version publiable : pas de nom, pas d'identifiant, GPS arrondis (~1 km)."""
    pub = base.drop(columns=["nom", "store_id", "AddressId", "ville", "code_postal"]).copy()
    pub.insert(0, "producteur", [f"P{i:04d}" for i in range(1, len(pub) + 1)])
    pub["lat"] = pub.lat.round(config.PRECISION_GPS)
    pub["lon"] = pub.lon.round(config.PRECISION_GPS)
    return pub
