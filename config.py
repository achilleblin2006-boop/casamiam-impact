"""
Paramètres du projet. C'est le seul fichier à modifier pour changer
de période d'analyse ou de fichiers sources.
"""
from pathlib import Path
import pandas as pd

RACINE = Path(__file__).parent
DOSSIER_RAW = RACINE / "data" / "raw"            # exports Metabase (jamais publiés)
DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_SORTIES = RACINE / "outputs"
DOSSIER_FIGURES = DOSSIER_SORTIES / "figures"

# Noms attendus des exports Metabase (renomme tes CSV comme ceci)
FICHIERS = {
    "ventes": "ventes_boutique_mois.csv",      # Order : Store ID, Store Name, mois, Nombre, Somme de Price, acheteurs
    "boutiques": "boutiques.csv",              # Store : ID, Name, Created At, Status, AddressId, liens réseaux
    "adresses": "adresses.csv",                # Address : ID, City, Zip Code, Longitude, Latitude
    "produits": "produits.csv",                # Product : StoreId, CategoryId, Visible, Nombre, Max Updated At
    "categories": "categories.csv",            # Category : ID, Name
    "points_retrait": "points_retrait.csv",    # Points de retrait : ID, AddressId, Store ID, Name
    "plateforme": "plateforme_mois.csv",       # Order par mois, toute la plateforme
}

# Données du scraper (abonnés suivis chaque semaine) : facultatives
FICHIERS_SCRAPING = {
    "producteurs": "scraping_producteurs.csv",   # 1 ligne par abonné : métier, abonnement, churn
    "etat": "scraping_etat.csv",                 # 1 ligne par abonné et par semaine : boutique, réseaux, QR
    "evenements": "scraping_evenements.csv",     # jalons datés : inscription, 1res commandes, posts…
}
MOIS_SCRAPING = [pd.Timestamp(2026, 7, 1), pd.Timestamp(2026, 8, 1), pd.Timestamp(2026, 9, 1)]  # mois complets couverts
SEUIL_CATALOGUE_RECENT_JOURS = 30
# Noms différents entre HubSpot et Metabase (nom normalisé HubSpot -> nom normalisé Metabase)
ALIAS_SCRAPING = {
    # "nom normalisé côté HubSpot": "nom normalisé côté Metabase",
    # (liste réelle non publiée : elle contient des noms de producteurs)
}

# Période d'analyse : 12 mois complets
DEBUT_PERIODE = pd.Timestamp(2025, 10, 1)
FIN_PERIODE = pd.Timestamp(2026, 9, 1)          # dernier mois inclus
DATE_REFERENCE = pd.Timestamp(2026, 10, 1)      # « aujourd'hui » pour l'ancienneté et la dormance

SEUIL_DORMANCE_MOIS = 3      # dormante = aucune vente depuis plus de 3 mois
SEUIL_CAMPAGNE = 0.5         # vente par campagnes = plus de 50 % du CA sur un seul mois
SEUIL_VENTE_SUR_PLACE_KM = 1

# Anonymisation des sorties publiques (GitHub, portfolio)
ANONYMISER = True
PRECISION_GPS = 2            # 2 décimales ≈ 1 km : on ne publie pas l'adresse exacte des fermes

# Boutiques de test à exclure (motifs dans le nom normalisé)
MOTIF_TEST = r"(?:\btest|\btoto\b|\bdemo\b)"  # motifs réels simplifiés pour la version publique

# Regroupement des 108 catégories Casamiam en familles (mots-clés, en minuscules)
FAMILLES = [
    ("Activités", ["activit", "atelier", "cours cuisine", "visite"]),
    ("Poisson et fruits de mer", ["poisson", "huitre", "moule", "coquillage", "de la mer"]),
    ("Viande et charcuterie", ["agneau", "bœuf", "porc", "volaille", "gibier", "charcuterie", "saucisse",
                               "saucisson", "brochette", "viande", "foie gras", "chevreau"]),
    ("Crèmerie et œufs", ["fromage", "crémerie", "beurre", "lait", "yaourt", "œufs"]),
    ("Boulangerie et pâtisserie", ["pain", "viennoiserie", "gâteau", "tarte", "patisserie", "biscuit",
                                   "quiche", "glace"]),
    ("Fruits et légumes", ["fruits de saison", "légume", "pommes", "champignon", "ail, oignons",
                           "cueillette", "plants"]),
    ("Boissons", ["vin", "bière", "champagne", "alcool", "gin", "jus", "limonade", "boisson", "café", "tisane"]),
    ("Traiteur et plats préparés", ["traiteur", "plats tout", "sandwich", "burger", "pizza", "sushi", "baraque",
                                    "couscous", "asie", "afrique", "apéro dinatoire", "gastronomique"]),
    ("Épicerie", ["epicerie", "confiture", "miel", "huile", "sel ", "sauce", "condiment", "pâtes et riz",
                  "farine", "muesli", "noix", "chocolat", "confiserie", "sucre", "tapenade", "chips",
                  "produits sucrés", "spiruline", "petits pots", "préparation", "spécialités", "conserves"]),
]
CATEGORIES_GENERIQUES = {"root", "à la une", "et aussi ..."}
