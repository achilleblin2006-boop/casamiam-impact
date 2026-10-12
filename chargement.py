"""
Chargement et nettoyage des exports Metabase.
Metabase exporte les dates en français (« mars 12, 2025, 10:58 AM »),
les nombres avec des virgules de milliers et les GPS en « 3.21° E » :
ce module convertit tout ça en formats exploitables.
"""
import re
import unicodedata

import numpy as np
import pandas as pd

import config

MOIS_FR = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
           "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}


def lire(cle):
    """Lit un export brut à partir de sa clé dans config.FICHIERS."""
    chemin = config.DOSSIER_RAW / config.FICHIERS[cle]
    if not chemin.exists():
        raise FileNotFoundError(f"Export manquant : {chemin}")
    return pd.read_csv(chemin, thousands=",", low_memory=False)


def mois_fr(texte):
    """« octobre, 2025 » -> Timestamp(2025-10-01)."""
    mois, annee = [x.strip() for x in str(texte).split(",")]
    return pd.Timestamp(int(annee), MOIS_FR[mois], 1)


def date_fr(texte):
    """« mars 12, 2025, 10:58 AM » -> Timestamp."""
    if pd.isna(texte):
        return pd.NaT
    mois, reste = str(texte).split(" ", 1)
    jour_annee = reste.split(",")
    return pd.Timestamp(int(jour_annee[1]), MOIS_FR[mois], int(jour_annee[0]))


def gps(texte):
    """« 3.21127900° E » -> 3.211279 (négatif pour W et S)."""
    if pd.isna(texte):
        return np.nan
    valeur = float(str(texte).split("°")[0])
    return -valeur if str(texte).strip().endswith(("W", "S")) else valeur


def normaliser(nom):
    """Nom simplifié pour comparer : sans accents, minuscules, sans ponctuation."""
    if pd.isna(nom):
        return None
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", nom).strip()


def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau (formule de haversine), vectorisée."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(h))


def charger_tout():
    """Charge les 7 exports, renomme les colonnes et convertit les formats."""
    ventes = lire("ventes").rename(columns={
        "Store ID": "store_id", "Store Name": "nom_vente", "Nombre": "commandes",
        "Somme de Price": "ca", "Valeurs distinctes de User ID": "acheteurs"})
    ventes["mois"] = ventes["Created At: Mois"].map(mois_fr)

    boutiques = lire("boutiques").rename(columns={"ID": "store_id", "Name": "nom", "Status": "statut"})
    boutiques["date_creation"] = boutiques["Created At"].map(date_fr)

    adresses = lire("adresses").rename(columns={"ID": "AddressId", "City": "ville", "Zip Code": "code_postal"})
    adresses["lat"] = adresses["Latitude"].map(gps)
    adresses["lon"] = adresses["Longitude"].map(gps)
    adresses["code_postal"] = adresses["code_postal"].astype("string").str.extract(r"(\d{4,5})")[0].str.zfill(5)

    produits = lire("produits").rename(columns={"StoreId → ID": "store_id"})
    categories = lire("categories").rename(columns={"ID": "CategoryId", "Name": "categorie"})
    points = lire("points_retrait").rename(columns={"ID": "point_id", "Store ID": "store_id", "Name": "nom_point"})

    plateforme = lire("plateforme").rename(columns={
        "Nombre": "commandes", "Somme de Price": "ca", "Valeurs distinctes de User ID": "acheteurs"})
    plateforme["mois"] = plateforme["Created At: Mois"].map(mois_fr)

    return {"ventes": ventes, "boutiques": boutiques, "adresses": adresses, "produits": produits,
            "categories": categories, "points": points, "plateforme": plateforme}
