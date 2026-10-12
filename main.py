"""
Point d'entrée : python main.py
Exécute toute la chaîne, des exports Metabase bruts jusqu'aux résultats.
"""
import config
import scraping
from analyses import comparer, indicateurs, rapport_markdown, regression_activation
from carte import produire_carte
from chargement import charger_tout
from construction import anonymiser, construire_base
from graphiques import tout_produire


def main():
    for dossier in (config.DOSSIER_PROCESSED, config.DOSSIER_SORTIES, config.DOSSIER_FIGURES):
        dossier.mkdir(parents=True, exist_ok=True)

    print("1/5 Chargement des exports Metabase…")
    donnees = charger_tout()

    print("2/5 Construction de la base boutiques…")
    base, points, categories = construire_base(donnees)
    base.to_csv(config.DOSSIER_PROCESSED / "base_boutiques_INTERNE.csv", index=False)   # jamais publiée
    anonymiser(base).to_csv(config.DOSSIER_PROCESSED / "base_boutiques_anonyme.csv", index=False)
    categories.to_csv(config.DOSSIER_PROCESSED / "categories_familles.csv", index=False)

    print("3/5 Analyses…")
    ind = indicateurs(base, points)
    pop = base[base.inclus_analyse]
    tables = {
        "Produits visibles et activation": comparer(pop, "tranche_produits"),
        "Lien Facebook renseigné dans la fiche": comparer(pop, "lien_facebook"),
        "Lien Instagram renseigné dans la fiche": comparer(pop, "lien_instagram"),
        "Phase": comparer(pop, "phase"),
        "Famille principale": comparer(pop, "famille_principale"),
    }
    modele, rapports = regression_activation(base)
    rapport_markdown(ind, tables, rapports, modele)

    print("4/5 Graphiques…")
    tout_produire(base, points, donnees["plateforme"], tables["Produits visibles et activation"])

    print("5/5 Carte…")
    produire_carte(base)

    if scraping.fichiers_presents():
        print("Bonus : données du scraper (abonnés)…")
        scraping.executer(base, donnees["ventes"])
        print(f"Résultats scraping : {config.DOSSIER_SORTIES / 'resultats_scraping.md'}")

    print(f"\nTerminé. {ind['boutiques_actives_12m']} boutiques actives sur {ind['boutiques_analysees']} analysées "
          f"({ind['taux_activation']:.0%}), {ind['ca_12m']:,.0f} € de CA sur 12 mois.")
    print(f"Résultats : {config.DOSSIER_SORTIES / 'resultats.md'}")


if __name__ == "__main__":
    main()
