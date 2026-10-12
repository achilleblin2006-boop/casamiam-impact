"""
Volet « pratiques réelles » : données du scraper sur les producteurs abonnés.

Le scraper suit chaque semaine (21/06 → 04/10/2026) les ~150 producteurs abonnés :
état de la boutique (produits, fraîcheur du catalogue), réseaux sociaux (lien Casamiam
en bio, posts avec lien), scans de QR codes, et des jalons datés (inscription,
abonnement, premières commandes, posts avec lien, churn).

Intérêt par rapport aux exports Metabase : on mesure ce que le producteur FAIT
vraiment (le lien est-il dans sa bio ? publie-t-il ?), et non ce qu'il a renseigné
dans sa fiche. Et le suivi hebdomadaire permet de comparer un producteur à lui-même.

Rappel : associations, pas causalités.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

import config
from chargement import normaliser

BOOLEENS = ["casamiam_bio_facebook", "casamiam_bio_instagram", "casamiam_bio_gmb", "post_epingle",
            "casamiam_dans_post_epingle", "fait_pub_meta", "photo_profil", "banniere", "description_renseignee",
            "avis_gmb_affiches", "boutique_facebook", "boutique_instagram", "boutique_tiktok", "boutique_linkedin",
            "boutique_gmb", "horaires_renseignes", "en_vacances", "site_actif", "site_contient_casamiam",
            "source_fb_ok", "source_ig_ok", "source_gmb_ok", "source_site_ok"]

METIERS = {"Magasin de fromages": "Commerce", "Magasin de producteurs": "Commerce", "Produits salés": "Autre",
           "Produits sucrés": "Autre", "Traiteur": "Autre", "Boissons": "Autre",
           "Eleveur lait/fromage": "Éleveur", "Eleveur viande": "Éleveur", "Boucher/Charcutier": "Boucher"}


def fichiers_presents():
    return all((config.DOSSIER_RAW / f).exists() for f in config.FICHIERS_SCRAPING.values())


def _bool(serie):
    """True/False/vide (texte ou booléen) -> 1.0 / 0.0 / NaN."""
    return serie.map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})


def charger():
    lire = lambda cle: pd.read_csv(config.DOSSIER_RAW / config.FICHIERS_SCRAPING[cle], low_memory=False)
    prod = lire("producteurs")
    for c in ["date_inscription", "date_abonnement", "date_churn"]:
        prod[c] = pd.to_datetime(prod[c], errors="coerce")
    prod["churn"] = prod.churn.astype(str).eq("True")
    etat = lire("etat")
    etat["date_debut_scrap"] = pd.to_datetime(etat.date_debut_scrap)
    etat["date_fin_scrap"] = pd.to_datetime(etat.date_fin_scrap)
    for c in BOOLEENS:
        if c in etat:
            etat[c] = _bool(etat[c])
    ev = lire("evenements")
    ev["date"] = pd.to_datetime(ev.date, errors="coerce", format="%Y-%m-%d")   # quelques dates sans année -> vides
    return prod, etat, ev


def joindre(prod, base):
    """
    Rattache chaque abonné HubSpot à sa boutique Metabase. L'identifiant « company_id_metabase »
    n'est pas l'ID de boutique des exports : la jointure se fait par nom normalisé (+ alias).
    En cas de doublon de nom côté Metabase, on garde la boutique qui a le plus vendu.
    """
    b = base.assign(k=base.nom.map(normaliser)).dropna(subset=["k"])
    b = b.sort_values("ca_total", ascending=False).drop_duplicates("k")
    prod = prod.assign(k=prod.nom_boutique.map(normaliser).replace(config.ALIAS_SCRAPING))
    return prod.merge(b[["k", "store_id"]], on="k", how="left")


def _caracteristiques(etat):
    """Résume les 14 semaines de scraping en une ligne par producteur."""
    g = etat.groupby("deal_id")
    f = pd.DataFrame({
        "produits_visibles": g.produits_visibles.mean(),
        "part_produits_visibles": g.produits_visibles_pct.mean(),
        "nb_familles": g.nb_familles.mean(),
        "jours_depuis_maj": g.jours_depuis_maj_catalogue.median(),
        "description": g.description_renseignee.mean(),
        "lien_bio_facebook": g.casamiam_bio_facebook.mean(),
        "lien_bio_instagram": g.casamiam_bio_instagram.mean(),
        "lien_site_perso": g.site_contient_casamiam.max(),
        "posts_fb_semaine": g.posts_fb_7j.mean(),
        "posts_avec_lien": g.fb_posts_avec_lien_casamiam_7j.sum(),
        "followers_facebook": g.followers_facebook.median(),
        "followers_instagram": g.followers_instagram.median(),
        "avis_google": g.avis_gmb.median(),
        "note_google": g.note_gmb.median(),
        "pub_meta": g.fait_pub_meta.max(),
        "fiche_lien_facebook": g.boutique_facebook.mean(),
        "scans_qr": g.scans_total.sum(),
        "avis_affiches": g.avis_gmb_affiches.mean(),
    })
    return f.astype(float)


def base_abonnes(prod, etat, ventes):
    """Une ligne par abonné : caractéristiques scrapées + ventes juillet-septembre 2026."""
    v = ventes[ventes.mois.isin(config.MOIS_SCRAPING)].groupby("store_id").agg(
        commandes=("commandes", "sum"), ca=("ca", "sum"))
    ab = prod.merge(v, left_on="store_id", right_index=True, how="left").fillna({"commandes": 0, "ca": 0})
    debut = ab.date_abonnement.dt.to_period("M").dt.to_timestamp().clip(lower=config.MOIS_SCRAPING[0])
    fin = config.MOIS_SCRAPING[-1]
    ab["mois_observes"] = ((fin.year - debut.dt.year) * 12 + (fin.month - debut.dt.month) + 1).clip(0, len(config.MOIS_SCRAPING))
    ab["ca_mensuel"] = (ab.ca / ab.mois_observes).where(ab.mois_observes > 0)
    ab["active"] = (ab.commandes > 0).astype(int)
    ab["metier_groupe"] = ab.metier.fillna("Autre").str.split(" - ").str[0].replace(METIERS)
    ab["anciennete_mois"] = ((config.MOIS_SCRAPING[0] - ab.date_abonnement).dt.days / 30.4).clip(lower=0)
    ab = ab.merge(_caracteristiques(etat), left_on="deal_id", right_index=True, how="left")
    ab["catalogue_recent"] = (ab.jours_depuis_maj < config.SEUIL_CATALOGUE_RECENT_JOURS).astype(int)
    ab["lien_bio"] = (ab.lien_bio_facebook >= 0.5).astype(int)
    ab["post_lien"] = (ab.posts_avec_lien > 0).astype(int)
    ab["site_lien"] = (ab.lien_site_perso > 0).astype(int)
    ab["inclus"] = ab.store_id.notna() & (ab.mois_observes > 0) & ~ab.churn
    return ab


def panel_mensuel(ab, etat, ev, ventes):
    """Une ligne par abonné et par mois (juillet, août, septembre) pour comparer un producteur à lui-même."""
    pop = ab[ab.inclus][["deal_id", "store_id"]]
    mois = pd.DataFrame({"mois": config.MOIS_SCRAPING})
    pan = pop.merge(mois, how="cross")
    v = ventes[ventes.mois.isin(config.MOIS_SCRAPING)][["store_id", "mois", "commandes"]]
    pan = pan.merge(v, on=["store_id", "mois"], how="left").fillna({"commandes": 0})
    posts = ev[ev.type == "post_lien_casamiam"].assign(mois=lambda x: x.date.dt.to_period("M").dt.to_timestamp())
    posts = posts.groupby(["deal_id", "mois"]).size().rename("posts_lien").reset_index()
    pan = pan.merge(posts, on=["deal_id", "mois"], how="left").fillna({"posts_lien": 0})
    em = (etat.assign(mois=etat.date_fin_scrap.dt.to_period("M").dt.to_timestamp())
          .groupby(["deal_id", "mois"]).jours_depuis_maj_catalogue.min().rename("maj_min").reset_index())
    pan = pan.merge(em, on=["deal_id", "mois"], how="left")
    pan["post_lien_mois"] = (pan.posts_lien > 0).astype(int)
    pan["catalogue_maj_mois"] = (pan.maj_min <= 31).astype(float).where(pan.maj_min.notna())
    pan["log_commandes"] = np.log1p(pan.commandes)
    return pan


def comparer_pratiques(pop):
    lignes = [("Lien Casamiam dans la bio Facebook", pop.lien_bio == 1),
              ("Lien renseigné dans la fiche Casamiam (champ Metabase)", pop.fiche_lien_facebook >= 0.5),
              ("Lien Casamiam sur son site", pop.site_lien == 1),
              ("Au moins un post Facebook avec le lien (14 sem.)", pop.post_lien == 1),
              ("Catalogue mis à jour il y a moins de 30 jours", pop.catalogue_recent == 1),
              ("Au moins un scan de QR code", pop.scans_qr > 0)]
    res = []
    for nom, masque in lignes:
        for etiquette, m in (("oui", masque), ("non", ~masque)):
            res.append({"pratique": nom, "groupe": etiquette, "producteurs": int(m.sum()),
                        "taux_activation": pop[m].active.mean(), "ca_mensuel_median": pop[m].ca_mensuel.median()})
    return pd.DataFrame(res)


def correlations(pop):
    variables = {"Produits visibles": "produits_visibles", "Jours depuis la dernière MAJ du catalogue": "jours_depuis_maj",
                 "Familles de produits": "nb_familles", "Posts Facebook avec lien (14 sem.)": "posts_avec_lien",
                 "Posts Facebook par semaine": "posts_fb_semaine", "Abonnés Facebook": "followers_facebook",
                 "Abonnés Instagram": "followers_instagram", "Avis Google": "avis_google", "Note Google": "note_google",
                 "Scans de QR codes (cumul)": "scans_qr"}
    res = []
    for nom, c in variables.items():
        x = pop[[c, "ca_mensuel"]].dropna()
        rho, p = spearmanr(x[c], x.ca_mensuel)
        res.append({"variable": nom, "n": len(x), "rho_spearman": rho, "p_value": p})
    return pd.DataFrame(res).sort_values("rho_spearman", key=abs, ascending=False)


def modeles(pop, panel):
    """Régressions transversale (entre producteurs) et intra-producteur (effets fixes)."""
    x = pop.dropna(subset=["jours_depuis_maj", "produits_visibles"]).assign(
        log_ca=lambda d: np.log1p(d.ca_mensuel), log_produits=lambda d: np.log1p(d.produits_visibles),
        log_anciennete=lambda d: np.log1p(d.anciennete_mois))
    base_f = "log_ca ~ log_produits + lien_bio + post_lien + site_lien + log_anciennete + C(metier_groupe)"
    complet = smf.ols(base_f + " + catalogue_recent", data=x).fit(cov_type="HC1")
    sans_maj = smf.ols(base_f, data=x).fit(cov_type="HC1")
    intra = smf.ols("log_commandes ~ post_lien_mois + C(mois) + C(deal_id)", data=panel).fit(
        cov_type="cluster", cov_kwds={"groups": panel.deal_id})
    p2 = panel.dropna(subset=["catalogue_maj_mois"])
    intra2 = smf.ols("log_commandes ~ post_lien_mois + catalogue_maj_mois + C(mois) + C(deal_id)", data=p2).fit(
        cov_type="cluster", cov_kwds={"groups": p2.deal_id})
    garder = ["catalogue_recent", "log_produits", "lien_bio", "post_lien", "site_lien", "log_anciennete"]
    libelles = {"catalogue_recent": "Catalogue mis à jour < 30 j", "log_produits": "Produits visibles (log)",
                "lien_bio": "Lien Casamiam en bio Facebook", "post_lien": "Posts avec lien",
                "site_lien": "Lien sur le site perso", "log_anciennete": "Ancienneté d'abonnement (log)",
                "post_lien_mois": "Mois avec un post lien", "catalogue_maj_mois": "Catalogue mis à jour dans le mois"}
    def tab(m, noms):
        noms = [n for n in noms if n in m.params]
        return pd.DataFrame({"effet_pct": (np.exp(m.params[noms]) - 1) * 100, "p_value": m.pvalues[noms]},
                            index=noms).rename(index=libelles)
    return {"transversal": (tab(complet, garder), complet), "transversal_sans_maj": (tab(sans_maj, garder), sans_maj),
            "intra": (tab(intra, ["post_lien_mois"]), intra),
            "intra_maj": (tab(intra2, ["post_lien_mois", "catalogue_maj_mois"]), intra2)}


def parcours(prod, ev):
    """Jalons : délais entre inscription, abonnement, premiers produits et premières commandes."""
    datees = ev[ev.detail.ne("legacy")].groupby(["deal_id", "type"]).date.min().unstack()
    atteint = pd.crosstab(ev.deal_id, ev.type) > 0
    delais = {}
    for a, b in [("inscription", "abonnement"), ("5_premiers_produits", "abonnement"),
                 ("3_premieres_commandes", "abonnement"), ("5_premiers_produits", "3_premieres_commandes")]:
        d = (datees[b] - datees[a]).dt.days.dropna()
        delais[f"{a} → {b}"] = {"n": len(d), "mediane_jours": d.median()}
    ab = prod.set_index("deal_id").date_abonnement
    cohorte = ab[(ab >= "2025-07-01") & (ab <= "2026-07-31")].index
    d3 = (datees.reindex(cohorte)["3_premieres_commandes"] - ab.reindex(cohorte)).dt.days
    return {"delais": delais, "atteint": atteint.sum().to_dict(), "cohorte": len(cohorte),
            "cohorte_3_commandes": atteint.reindex(cohorte)["3_premieres_commandes"].fillna(False).mean(),
            "cohorte_3_commandes_30j": (d3 <= 30).sum() / len(cohorte)}


def qualite(prod, etat, ev):
    """Contrôles automatiques de cohérence du scraper."""
    sem = etat.groupby("date_debut_scrap").scans_total.sum()
    derniere = etat[etat.date_debut_scrap == etat.date_debut_scrap.max()]
    flicker = etat.dropna(subset=["casamiam_bio_gmb"]).groupby("deal_id").casamiam_bio_gmb.nunique()
    semaines = pd.date_range(etat.date_debut_scrap.min(), etat.date_debut_scrap.max(), freq="7D")
    return [
        ("Semaines manquantes", ", ".join(d.strftime("%d/%m") for d in semaines.difference(etat.date_debut_scrap.unique())) or "aucune"),
        ("Scans QR : semaines avec au moins un scan", f"{(sem > 0).sum()} sur {len(sem)} (tout le volume sur la 1re semaine)"),
        ("Lien en bio Google : producteurs dont la valeur change d'une semaine à l'autre", f"{(flicker > 1).sum()} sur {len(flicker)}"),
        ("Abonnés Facebook = 1 (valeur suspecte), dernière semaine", int((derniere.followers_facebook == 1).sum())),
        ("Taux d'engagement Facebook > 100 %", int((etat.engagement_fb_pct > 100).sum())),
        ("« Horaires renseignés » toujours faux", bool(etat.horaires_renseignes.eq(0).all())),
        ("« nb_erreurs » toujours à 0 alors que des sources échouent", f"{bool(etat.nb_erreurs.eq(0).all())} ; échecs Facebook : {int(etat.source_fb_ok.eq(0).sum())} lignes"),
        ("Jalons « legacy » sans date (antérieurs au scraper)", int((ev.detail.eq("legacy") & ev.date.isna()).sum())),
        ("Autres jalons sans date exploitable (ex. « 10 May » sans année)", int((ev.detail.ne("legacy") & ev.date.isna()).sum())),
        ("Identifiant Metabase manquant (« ? »)", int(prod.company_id_metabase.eq("?").sum())),
    ]


def executer(base, ventes):
    """Appelée par main.py si les fichiers du scraper sont présents."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    prod, etat, ev = charger()
    prod = joindre(prod, base)
    ab = base_abonnes(prod, etat, ventes)
    pop = ab[ab.inclus]
    panel = panel_mensuel(ab, etat, ev, ventes)
    comp, corr, mods, parc, qual = comparer_pratiques(pop), correlations(pop), modeles(pop, panel), parcours(prod, ev), qualite(prod, etat, ev)

    periode = ventes.mois.between(config.DEBUT_PERIODE, config.FIN_PERIODE)
    part_ca = ventes[periode & ventes.store_id.isin(prod.store_id)].ca.sum() / ventes[periode].ca.sum()

    # Figures
    VERT, GRIS = "#2E4A4C", "#B8C4C4"
    for nom, sous in [("07_pratiques_activation.png", comp)]:
        piv = sous.pivot(index="pratique", columns="groupe", values="taux_activation").loc[[r for r in comp.pratique.unique()]]
        fig, ax = plt.subplots(figsize=(8, 4.2))
        y = np.arange(len(piv))
        ax.barh(y + 0.2, piv["oui"] * 100, 0.4, color=VERT, label="Oui")
        ax.barh(y - 0.2, piv["non"] * 100, 0.4, color=GRIS, label="Non")
        ax.set_yticks(y, piv.index, fontsize=8)
        ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("Abonnés ayant vendu en juillet-septembre 2026 (%)")
        ax.legend(frameon=False, loc="lower right"); ax.set_title("Pratiques réelles et activation des abonnés")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        fig.tight_layout(); fig.savefig(config.DOSSIER_FIGURES / nom, dpi=200); plt.close(fig)
    x = pop.dropna(subset=["jours_depuis_maj"])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.scatter(x.jours_depuis_maj.clip(upper=400), x.ca_mensuel, s=14, color=VERT, alpha=0.6)
    ax.set_yscale("symlog", linthresh=10); ax.set_xlabel("Jours depuis la dernière mise à jour du catalogue (médiane, plafonné à 400)")
    ax.set_ylabel("CA mensuel juil.-sept. (€, échelle log)"); ax.set_title("Fraîcheur du catalogue et chiffre d'affaires")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(config.DOSSIER_FIGURES / "08_fraicheur_catalogue.png", dpi=200); plt.close(fig)

    # Rapport
    p, e = (lambda v: f"{v:.0%}"), (lambda v: "–" if pd.isna(v) else f"{v:,.0f} €".replace(",", " "))
    c2 = comp.copy(); c2["taux_activation"] = c2.taux_activation.map(p); c2["ca_mensuel_median"] = c2.ca_mensuel_median.map(e)
    k = corr.copy(); k["rho_spearman"] = k.rho_spearman.round(2); k["p_value"] = k.p_value.map(lambda v: f"{v:.3f}")
    fmt = lambda t: t.assign(effet_pct=t.effet_pct.map(lambda v: f"{v:+.0f} %"), p_value=t.p_value.map(lambda v: f"{v:.3f}")).to_markdown()
    m_t, mod_t = mods["transversal"]
    lignes = [
        "# Résultats – pratiques réelles des abonnés (scraper, 21/06 → 04/10/2026)",
        "Associations, pas causalités.\n",
        "## Chiffres clés",
        f"- Abonnés suivis : {len(prod)} ; rattachés à une boutique Metabase : {int(prod.store_id.notna().sum())} ; analysés (hors churn) : {len(pop)}",
        f"- Part du CA 12 mois de la plateforme réalisée par ces abonnés : {p(part_ca)}",
        f"- Abonnés ayant vendu en juillet-septembre 2026 : {p(pop.active.mean())} ; CA mensuel médian des actifs : {e(pop[pop.active == 1].ca_mensuel.median())}",
        f"- Abonnés avec le lien Casamiam en bio Facebook : {int(pop.lien_bio.sum())} ; dont lien aussi renseigné dans la fiche : {int(((pop.lien_bio == 1) & (pop.fiche_lien_facebook >= .5)).sum())}",
        f"- Cohorte abonnée 07/2025-07/2026 : {parc['cohorte']} producteurs, {p(parc['cohorte_3_commandes'])} ont atteint 3 commandes ({p(parc['cohorte_3_commandes_30j'])} dans les 30 jours suivant l'abonnement)",
        "\n## Pratiques et activation", c2.to_markdown(index=False),
        "\n## Corrélations avec le CA mensuel (Spearman)", k.to_markdown(index=False),
        f"\n## Modèle entre producteurs (log du CA mensuel, contrôle métier ; R² = {mod_t.rsquared:.2f}, n = {int(mod_t.nobs)})", fmt(m_t),
        "\nMême modèle sans la fraîcheur du catalogue (possible causalité inverse) :", fmt(mods["transversal_sans_maj"][0]),
        "\n## Modèle intra-producteur (même abonné d'un mois à l'autre, effets fixes producteur et mois)", fmt(mods["intra"][0]),
        "\nAvec la mise à jour du catalogue :", fmt(mods["intra_maj"][0]),
        "\n## Parcours (dates réelles, hors jalons « legacy »)",
        pd.DataFrame(parc["delais"]).T.to_markdown(),
        "\n## Churn", prod[prod.churn][["metier", "date_abonnement", "date_churn", "motif_churn"]].to_markdown(index=False),
        "\n## Contrôles qualité du scraper", pd.DataFrame(qual, columns=["contrôle", "résultat"]).to_markdown(index=False),
    ]
    (config.DOSSIER_SORTIES / "resultats_scraping.md").write_text("\n".join(lignes), encoding="utf-8")
    pop.drop(columns=["nom_boutique", "url_hubspot", "url_boutique", "company_id_hubspot", "company_id_metabase", "store_id", "k", "ville"]).assign(
        deal_id=lambda d: [f"A{i:03d}" for i in range(1, len(d) + 1)]).to_csv(config.DOSSIER_PROCESSED / "abonnes_anonyme.csv", index=False)
    return {"part_ca": part_ca, "pop": pop, "panel": panel, "comparaison": comp, "correlations": corr,
            "modeles": mods, "parcours": parc, "qualite": qual}
