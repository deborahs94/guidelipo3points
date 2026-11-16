# Dérush automatique (vidéos face caméra)

```
python3 derush.py MA_VIDEO.mp4 --script MON_SCRIPT.txt
```

Produit `MA_VIDEO_derush.mp4` et `MA_VIDEO_derush_rapport.json` (toutes les décisions et vérifications).

## Ce que fait l'outil

1. **Transcription mot par mot**, hésitations comprises :
   - ElevenLabs Scribe (`scribe_v1`) si une clé est présente (variable `ELEVENLABS_API_KEY` ou fichier `~/.elevenlabs_key`) et qu'il reste du crédit ;
   - sinon Whisper en local (modèle `medium` par défaut, `--modele turbo` possible).
   Le moteur utilisé, et pourquoi, est toujours affiché.
2. **Repérage des ratés** : alignement mot à mot avec le script. Mots en trop = reprise ou hésitation, à couper.
   Phrase recommencée = on garde la **dernière** prise.
   Un mot ajouté hors script qui n'est ni une reprise ni une hésitation est **gardé** (option `--couper-ajouts` pour le couper aussi).
3. **Coupes dans le silence** : le seuil de silence est calibré sur le fichier (entre le bruit de fond et la voix).
   S'il n'y a pas de vrai silence autour d'une reprise, elle n'est **pas** coupée et le rapport le signale.
4. **Coupes calées sur les images** de la vidéo : le son et l'image restent synchronisés.
5. **Vérifications automatiques** :
   - niveau sonore juste avant et juste après chaque coupe, et au raccord dans la vidéo finale (doit être sous le seuil de silence) ;
   - aucun mot gardé ne chevauche une coupe ;
   - retranscription de la vidéo coupée et comparaison mot à mot avec l'originale.
   Si un mot à garder a été touché, la coupe est rétrécie ou annulée, puis tout est revérifié (3 passes maximum).

## Test

```
python3 test/fabriquer_video_test.py video_test.mp4
python3 derush.py video_test.mp4 --script video_test_script.txt
```

Nécessite : ffmpeg, Python 3 avec numpy, scipy, openai-whisper (et `requests` pour ElevenLabs).
