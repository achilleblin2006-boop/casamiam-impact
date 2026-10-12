"""
Carte interactive des producteurs actifs (outputs/carte_producteurs.html).
Version anonymisée : pas de nom, position arrondie à ~1 km, CA en tranches.
"""
import folium
import numpy as np

import config

COULEURS = {"Fruits et légumes": "#4C9A2A", "Viande et charcuterie": "#B23A48", "Épicerie": "#C98B2B",
            "Boulangerie et pâtisserie": "#D4A373", "Crèmerie et œufs": "#6C8EBF", "Boissons": "#7B4B94",
            "Traiteur et plats préparés": "#E07A5F", "Poisson et fruits de mer": "#3D7EA6"}


def tranche_ca(ca):
    for seuil, libelle in [(500, "moins de 500 €"), (2000, "500 à 2 000 €"), (5000, "2 000 à 5 000 €")]:
        if ca < seuil:
            return libelle
    return "plus de 5 000 €"


def produire_carte(base):
    pop = base[base.inclus_analyse & base.active_12m & base.lat.notna()]
    # Fond de carte Esri : fonctionne aussi quand la carte est ouverte depuis un fichier local
    # (les serveurs OpenStreetMap bloquent ce cas avec une erreur 403).
    carte = folium.Map(location=[47.0, 2.5], zoom_start=6, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors",
        name="Fond Esri", max_zoom=16).add_to(carte)
    for _, b in pop.iterrows():
        lat, lon = (round(b.lat, config.PRECISION_GPS), round(b.lon, config.PRECISION_GPS)) if config.ANONYMISER else (b.lat, b.lon)
        famille = b.famille_principale if isinstance(b.famille_principale, str) else "Autre"
        texte = f"<b>{famille}</b><br>CA 12 mois : {tranche_ca(b.ca_12m)}<br>{b.commandes_12m} commandes"
        if not config.ANONYMISER:
            texte = f"<b>{b.nom}</b><br>" + texte
        folium.CircleMarker(location=[lat, lon], radius=float(3 + 2 * np.log1p(b.ca_12m / 100)),
                            color=COULEURS.get(famille, "#888888"), fill=True, fill_opacity=0.7, weight=1,
                            popup=folium.Popup(texte, max_width=220)).add_to(carte)
    legende = "".join(f'<div><span style="color:{c}">●</span> {f}</div>' for f, c in COULEURS.items())
    carte.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:20px;left:20px;z-index:999;background:white;padding:8px 10px;'
        f'border-radius:6px;font-size:12px;box-shadow:0 1px 4px #999"><b>Producteurs actifs (12 mois)</b>{legende}'
        '<div style="color:#666;margin-top:4px">Taille du cercle = CA</div></div>'))
    carte.save(config.DOSSIER_SORTIES / "carte_producteurs.html")
