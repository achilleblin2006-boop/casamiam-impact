"""
Génère des exports Metabase FICTIFS (mêmes colonnes, mêmes formats que les vrais)
pour faire tourner le projet sans les données internes de Casamiam.

    python demo/generer_donnees_fictives.py
    python main.py

Les fichiers sont écrits dans data/raw/. Aucune donnée réelle n'est utilisée :
noms, positions, produits et ventes sont tirés au hasard.
"""
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
N_BOUTIQUES = 400
MOIS = pd.date_range("2021-01-01", "2026-09-01", freq="MS")
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]
CATEGORIES = ["Fruits de saison", "Légumes", "Pommes", "Champignons", "Viande de bœuf", "Porc", "Volaille",
              "Charcuterie", "Fromage", "Œufs", "Beurre et crème", "Pain", "Viennoiseries", "Gâteaux",
              "Miel", "Confitures", "Huiles", "Farine", "Vin", "Bière", "Jus de fruits", "Traiteur",
              "Plats tout prêts", "Poisson", "Huîtres", "Activités", "À la une", "Root"]


def uid():
    return str(uuid.UUID(int=int(RNG.integers(0, 2**63)) << 64 | int(RNG.integers(0, 2**63))))


def mois_txt(m):
    return f"{MOIS_FR[m.month - 1]}, {m.year}"


def date_txt(d):
    return f"{MOIS_FR[d.month - 1]} {d.day}, {d.year}, 10:00 AM"


def gps_txt(lat, lon):
    return f"{abs(lon):.8f}° {'E' if lon >= 0 else 'W'}", f"{abs(lat):.8f}° {'N' if lat >= 0 else 'S'}"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    cats = pd.DataFrame({"ID": [uid() for _ in CATEGORIES], "Name": CATEGORIES})

    boutiques, adresses, produits, points, ventes = [], [], [], [], []
    for i in range(1, N_BOUTIQUES + 1):
        sid, aid = uid(), uid()
        # Producteurs fictifs, majoritairement dans les Hauts-de-France
        if RNG.random() < 0.75:
            lat, lon = RNG.uniform(49.6, 51.0), RNG.uniform(1.8, 4.2)
        else:
            lat, lon = RNG.uniform(43.5, 49.0), RNG.uniform(-1.0, 6.5)
        lo, la = gps_txt(lat, lon)
        adresses.append([aid, f"Commune {i:03d}", f"{RNG.integers(10000, 95999)}", lo, la])
        creation = pd.Timestamp("2023-03-01") + pd.Timedelta(days=int(RNG.integers(0, 1250)))
        reseau = lambda p: "https://exemple.org/page" if RNG.random() < p else None
        boutiques.append([sid, date_txt(creation), date_txt(creation), f"Producteur fictif {i:03d}", aid, "created",
                          reseau(0.25), None, reseau(0.15), None, reseau(0.35)])

        # Catalogue : beaucoup de boutiques sans produit visible, quelques catalogues fournis
        nb_visibles = int(RNG.choice([0, 0, 0, 2, 4, 8, 12, 20, 35, 50]))
        for cat in RNG.choice(cats.ID[:-2], size=int(RNG.integers(1, 4)), replace=False):
            produits.append([sid, cat, int(nb_visibles > 0), max(1, nb_visibles // 2 + int(RNG.integers(0, 3))),
                             date_txt(pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(RNG.integers(0, 260))))])

        # Points de retrait : presque toujours chez le producteur
        for _ in range(int(RNG.integers(1, 3))):
            pid_adr = uid()
            if RNG.random() < 0.9:
                plat, plon = lat + RNG.normal(0, 0.002), lon + RNG.normal(0, 0.002)
            else:
                plat, plon = lat + RNG.normal(0, 0.2), lon + RNG.normal(0, 0.2)
            lo, la = gps_txt(plat, plon)
            adresses.append([pid_adr, "", "", lo, la])
            points.append([uid(), pid_adr, sid, "", 0, "", f"Point de retrait {i:03d}"])

        # Ventes : la probabilité de vendre augmente avec le nombre de produits visibles
        p_vendre = 0.08 + 0.85 * min(nb_visibles, 40) / 40
        if RNG.random() < p_vendre:
            debut = max(creation, MOIS[0])
            panier = RNG.uniform(15, 45)
            intensite = RNG.lognormal(1.2, 1.0)
            for m in MOIS[MOIS >= debut.to_period("M").to_timestamp()]:
                if RNG.random() < 0.55:
                    n = int(RNG.poisson(intensite)) + 1
                    ventes.append([mois_txt(m), sid, f"Producteur fictif {i:03d}", n,
                                   round(n * panier * RNG.uniform(0.8, 1.2), 2), max(1, int(n * 0.8))])

    pd.DataFrame(boutiques, columns=["ID", "Created At", "Updated At", "Name", "AddressId", "Status", "Instagram URL",
                                     "Tiktok URL", "Google Business Profile URL", "Linkedin URL", "Facebook URL"]
                 ).to_csv(RAW / "boutiques.csv", index=False)
    pd.DataFrame(adresses, columns=["ID", "City", "Zip Code", "Longitude", "Latitude"]).to_csv(RAW / "adresses.csv", index=False)
    cats.to_csv(RAW / "categories.csv", index=False)
    pd.DataFrame(produits, columns=["StoreId → ID", "CategoryId", "Visible", "Nombre", "Max de Updated At: Mois"]
                 ).to_csv(RAW / "produits.csv", index=False)
    pd.DataFrame(points, columns=["ID", "AddressId", "Store ID", "Opening Hours", "Is Hidden", "Description", "Name"]
                 ).to_csv(RAW / "points_retrait.csv", index=False)
    v = pd.DataFrame(ventes, columns=["Created At: Mois", "Store ID", "Store Name", "Nombre", "Somme de Price",
                                      "Valeurs distinctes de User ID"])
    v.to_csv(RAW / "ventes_boutique_mois.csv", index=False)
    plat = (v.assign(_m=pd.to_datetime([pd.Timestamp(int(x.split(", ")[1]), MOIS_FR.index(x.split(",")[0]) + 1, 1)
                                        for x in v["Created At: Mois"]]))
            .groupby("_m").agg({"Nombre": "sum", "Somme de Price": "sum", "Valeurs distinctes de User ID": "sum"})
            .reset_index())
    plat.insert(0, "Created At: Mois", plat.pop("_m").map(mois_txt))
    plat.to_csv(RAW / "plateforme_mois.csv", index=False)
    print(f"Données fictives écrites dans {RAW} : {N_BOUTIQUES} boutiques, {v.Nombre.sum():,} commandes.")


if __name__ == "__main__":
    main()
