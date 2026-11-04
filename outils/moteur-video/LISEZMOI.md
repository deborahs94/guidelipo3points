# Moteur vidéo « style signature » (Remotion)

Compose toute une vidéo face caméra au style de Déborah (skill `mon-style-signature`) à partir de :
- la vidéo (dérushée de préférence avec `../derush`),
- un fichier d'effets `effets.json` (temps en **secondes**),
- une musique facultative.

## Utilisation

```
npm install
python3 fabriquer.py apercus MA_VIDEO.mp4 effets.json [--musique musique.mp3]
# -> vérifier out/apercus/planche.png (une image fixe par animation)
python3 fabriquer.py rendu --sortie out/ma_video.mp4
# -> rendu complet, puis volume final -14 LUFS (crête -1 dBTP)
```

Si le rendu plante au démarrage (« Target closed », « icudtl.dat ») :
`REMOTION_CHROME_MODE=chrome-for-testing python3 fabriquer.py rendu`.
Par défaut, le moteur utilise le Chromium headless déjà installé sur la machine (`REMOTION_CHROME` pour en choisir un autre).

## effets.json

```json
{
  "script": "Le texte prévu : il sert d'orthographe de référence pour les sous-titres.",
  "mots_cles": ["cellulite", "faute"],
  "coupes": [2.35, 4.3],
  "chapitres": [{"debut": 0, "titre": "Le problème"}, {"debut": 4.3, "titre": "La vérité"}],
  "ambiance": {"grain": 0.05, "etalonnage": true, "chaleur": 0.06},
  "fond": "auto",
  "effets": [ ... ]
}
```

| type | champs | ce que ça fait |
|---|---|---|
| `accroche` | `surtitre`, `titre`, `motFort` | sur-titre en petites majuscules + titre Playfair qui s'écrit lettre par lettre |
| `grand_titre` | `texte`, `motFort` | phrase choc en très grand, visage flouté derrière, entrée en 3D |
| `icone` | `icone` (coeur, check, etoile, goutte, eclair, cible), `position` (droite, gauche, haut), `texte` | rebond + particules |
| `compteur` | `valeur`, `decimales`, `prefixe`, `suffixe`, `libelle` | chiffre qui défile, sur carte crème |
| `carte` | `contenu`: `chiffre` (valeur…), `entonnoir` (`etapes`), `chat` (`question`, `reponse`, `nom`), `checklist` (`titre`, `elements`) | la vidéo se réduit en carte arrondie, l'animation joue dessous |
| `zoom` | `force` (1.2 = +20 %) | zoom avec flou de mouvement |
| `transition` | `style`: `lumiere` ou `panoramique` | lumière colorée ou panoramique rapide, centrés sur `debut` |
| `fin` | `nom`, `sousTitre`, `compte`, `motCle` | carte de fin avec le nom |

Chaque effet a `debut` et `fin` (secondes). Un son discret est ajouté automatiquement
(whoosh, montée, impact, pop, scintillement, tic, tous générés avec ffmpeg dans `public/sons`).
`"son": false` le coupe, `"son": "impact"` le remplace, `"volumeSon": 0.3` le règle.

Toujours actifs : sous-titres mot à mot (2 à 4 mots, mot dit en couleur d'accent, mots-clés en Playfair italique),
changement de cadrage à chaque coupe, lente avancée, grain, étalonnage léger, barre de chapitres.

Musique : placée 20 dB sous la voix pendant la parole, elle remonte de 6 dB dans les silences.

## Fichiers

- `preparer.py` : transcription (ElevenLabs Scribe ou Whisper), sons, mesures de volume, `props.json`
- `src/` : la composition Remotion (`Signature.tsx`) et ses animations (`composants/`)
- `src/style.ts` : la charte (couleurs, polices, zone sûre, tailles de sous-titres)
- `exemples/` : l'essai de 10 s et un catalogue des cartes
- `test/fabriquer_rush_test.py` : rush de test (personnage dessiné + voix de synthèse)
