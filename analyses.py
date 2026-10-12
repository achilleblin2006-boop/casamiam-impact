"""
Analyses : indicateurs clés, facteurs associés à la performance, impact circuit court.
Rappel : toutes les relations mesurées sont des ASSOCIATIONS, pas des causalités.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config


def comparer(pop, colonne):
    """Taux d'activation et CA mensuel médian (boutiques actives) par modalité d'une variable."""
    actives = pop[pop.active_12m]
    tab = pop.groupby(colonne, observed=True).agg(boutiques=("active_12m", "size"),
                                                   taux_activation=("active_12m", "mean"))
    tab["ca_mensuel_median_actives"] = actives.groupby(colonne, observed=True).ca_mensuel.median()
    return tab


def indicateurs(base, points):
    pop = base[base.inclus_analyse]
    actives = pop[pop.active_12m]
    ca_trie = actives.ca_12m.sort_values(ascending=False)
    avec_dist = actives[actives.distance_moy_km.notna()]
    ind = {
        "boutiques_analysees": len(pop),
        "boutiques_actives_12m": int(pop.active_12m.sum()),
        "taux_activation": pop.active_12m.mean(),
        "ca_12m": actives.ca_12m.sum(),
        "commandes_12m": int(actives.commandes_12m.sum()),
        "ca_mensuel_median_actives": actives.ca_mensuel.median(),
        "part_ca_top20": ca_trie.head(20).sum() / ca_trie.sum(),
        "boutiques_0_produit": int((pop.nb_produits_visibles == 0).sum()),
        "jamais_vendu": int((pop.etat_activite == "Jamais vendu").sum()),
        "dormantes": int((pop.etat_activite == "Dormante").sum()),
        "part_dormantes_parmi_ayant_vendu": (pop.etat_activite == "Dormante").sum() / (pop.commandes_total > 0).sum(),
        "departements_actifs": actives.departement.nunique(),
        "part_points_sur_place": (points.distance_km < config.SEUIL_VENTE_SUR_PLACE_KM).mean(),
        "part_ca_sur_place": avec_dist[avec_dist.distance_moy_km < config.SEUIL_VENTE_SUR_PLACE_KM].ca_12m.sum() / avec_dist.ca_12m.sum(),
        "part_ca_moins_50km": avec_dist[avec_dist.distance_moy_km <= 50].ca_12m.sum() / avec_dist.ca_12m.sum(),
    }
    return ind


def regression_activation(base):
    """
    Régression logistique : probabilité d'avoir vendu sur 12 mois selon plusieurs facteurs
    pris ENSEMBLE. Permet de voir si le nombre de produits reste associé à l'activation
    une fois les liens réseaux, l'ancienneté et la famille de produits pris en compte.
    """
    pop = base[base.inclus_analyse & base.famille_principale.notna()].copy()
    pop["active"] = pop.active_12m.astype(int)
    pop["log_produits"] = np.log1p(pop.nb_produits_visibles)
    pop["facebook"] = pop.lien_facebook.astype(int)
    pop["instagram"] = pop.lien_instagram.astype(int)
    pop["neo"] = (pop.phase == "Néo-entrant (<6 mois)").astype(int)
    # Les familles trop rares (< 15 boutiques) sont écartées : trop peu de cas pour estimer un effet
    effectifs = pop.famille_principale.value_counts()
    pop = pop[pop.famille_principale.map(effectifs) >= 15]
    pop["famille"] = pop.famille_principale
    modele = smf.logit("active ~ log_produits + facebook + instagram + neo "
                       "+ C(famille, Treatment('Fruits et légumes'))", data=pop).fit(disp=False, maxiter=200)
    rapports = pd.DataFrame({"odds_ratio": np.exp(modele.params), "p_value": modele.pvalues}).drop(index="Intercept")
    libelles = {"log_produits": "Nombre de produits visibles (log)", "facebook": "Lien Facebook renseigné",
                "instagram": "Lien Instagram renseigné", "neo": "Néo-entrant (< 6 mois)"}
    rapports.index = [libelles.get(i, i.split("[T.")[-1].rstrip("]") + " (vs fruits et légumes)") for i in rapports.index]
    return modele, rapports.sort_values("p_value")


def rapport_markdown(ind, tables, rapports, modele):
    """Écrit outputs/resultats.md : les chiffres clés, prêts à reprendre dans la note."""
    p = lambda x: f"{x:.0%}"
    e = lambda x: f"{x:,.0f} €".replace(",", " ")
    lignes = [
        "# Résultats – performance et impact des producteurs Casamiam",
        f"Période : {config.DEBUT_PERIODE:%m/%Y} – {config.FIN_PERIODE:%m/%Y}. Associations, pas causalités.\n",
        "## Chiffres clés",
        f"- Boutiques analysées : {ind['boutiques_analysees']} ; actives sur 12 mois : {ind['boutiques_actives_12m']} ({p(ind['taux_activation'])})",
        f"- CA généré pour les producteurs : {e(ind['ca_12m'])} ({ind['commandes_12m']} commandes)",
        f"- CA mensuel médian d'une boutique active : {e(ind['ca_mensuel_median_actives'])}",
        f"- Part du CA réalisée par les 20 premières boutiques : {p(ind['part_ca_top20'])}",
        f"- Boutiques sans aucun produit visible : {ind['boutiques_0_produit']}",
        f"- Boutiques dormantes : {ind['dormantes']} ({p(ind['part_dormantes_parmi_ayant_vendu'])} de celles qui ont déjà vendu)",
        "\n## Impact circuit court",
        f"- Points de retrait à moins de 1 km du producteur : {p(ind['part_points_sur_place'])}",
        f"- Part du CA réalisée sur place (< 1 km) : {p(ind['part_ca_sur_place'])} ; à 50 km ou moins : {p(ind['part_ca_moins_50km'])}",
        f"- Départements avec au moins un producteur actif : {ind['departements_actifs']}",
        "- Limite : distance producteur → point de retrait, pas le trajet des clients.",
    ]
    for titre, tab in tables.items():
        t = tab.copy()
        t["taux_activation"] = t.taux_activation.map(p)
        t["ca_mensuel_median_actives"] = t.ca_mensuel_median_actives.map(lambda x: "–" if pd.isna(x) else e(x))
        lignes += [f"\n## {titre}", t.to_markdown()]
    r = rapports.copy()
    r["odds_ratio"] = r.odds_ratio.round(2)
    r["p_value"] = r.p_value.map(lambda x: f"{x:.3f}")
    lignes += ["\n## Régression logistique (probabilité d'avoir vendu sur 12 mois)",
               f"Pseudo-R² : {modele.prsquared:.2f} ; observations : {int(modele.nobs)}.",
               "Lecture : un odds ratio > 1 signifie une association positive, toutes choses égales par ailleurs.",
               r.to_markdown()]
    (config.DOSSIER_SORTIES / "resultats.md").write_text("\n".join(lignes), encoding="utf-8")
