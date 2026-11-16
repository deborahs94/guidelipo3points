#!/usr/bin/env python3
"""Fabrique une vidéo au style signature, en 3 étapes :

  python3 fabriquer.py apercus MA_VIDEO.mp4 effets.json [--musique musique.mp3]
      -> prépare tout, puis rend une image fixe de chaque animation dans out/apercus/planche.png
         (à vérifier AVANT le rendu complet)
  python3 fabriquer.py rendu --sortie out/ma_video.mp4
      -> rendu complet avec les props déjà préparées, puis volume final à -14 LUFS (crête -1 dBTP)

Variables utiles : REMOTION_CHROME_MODE=chrome-for-testing si le rendu plante au démarrage
(« Target closed » ou « icudtl.dat »).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ICI, "out")


def sh(cmd, **kw):
    print("  $ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, cwd=ICI, **kw)


def remotion(args):
    try:
        sh(["npx", "remotion"] + args)
    except subprocess.CalledProcessError:
        print("\n⚠ Le rendu Remotion a échoué. Si l'erreur parle de « Target closed » ou « icudtl.dat », relance avec :\n"
              "  REMOTION_CHROME_MODE=chrome-for-testing python3 fabriquer.py ...\n")
        raise


def images_a_verifier(props):
    """Une image au cœur de chaque animation (+ une juste après son entrée)."""
    fps, duree = props["fps"], props["duree"]
    temps = {0.5}
    for e in props["effets"]:
        d, f = e["debut"], e["fin"]
        if e["type"] == "transition":
            temps.update({d - 0.1, d + 0.05})
        else:
            temps.update({d + min(0.35, (f - d) / 3), d + (f - d) * 0.7})
    return sorted({min(int(duree * fps) - 1, max(0, round(t * fps))) for t in temps})


def apercus(a):
    cmd = [sys.executable, "preparer.py", a.video, a.effets]
    if a.musique:
        cmd += ["--musique", a.musique]
    sh(cmd)
    props = json.load(open(os.path.join(ICI, "props.json"), encoding="utf-8"))
    images = images_a_verifier(props)
    dossier = os.path.join(OUT, "apercus")
    shutil.rmtree(dossier, ignore_errors=True)
    remotion(["render", "src/index.ts", "Signature", dossier, "--props=props.json",
              "--frames=" + ",".join(map(str, images)), "--image-format=png"])
    cols = min(8, len(images))
    sh(["ffmpeg", "-v", "error", "-y", "-pattern_type", "glob", "-i", os.path.join(dossier, "element-*.png"),
        "-vf", f"scale=270:480,tile={cols}x{(len(images) + cols - 1) // cols}", "-frames:v", "1",
        os.path.join(dossier, "planche.png")])
    print(f"▶ {len(images)} images à vérifier : {os.path.join(dossier, 'planche.png')}")


def rendu(a):
    brut = os.path.join(OUT, "rendu_brut.mp4")
    remotion(["render", "src/index.ts", "Signature", brut, "--props=props.json"])
    props = json.load(open(os.path.join(ICI, "props.json"), encoding="utf-8"))
    # volume final -14 LUFS intégré, crête vraie max -1 dBTP (cible -1,5 pour la marge de l'AAC)
    mesure = subprocess.run(["ffmpeg", "-v", "info", "-i", brut, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                             "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(mesure[mesure.rindex("{"):mesure.rindex("}") + 1])
    filtre = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
              "linear=true,aresample=48000")
    sh(["ffmpeg", "-v", "error", "-y", "-i", brut, "-c:v", "copy", "-af", filtre, "-c:a", "aac", "-b:a", "192k",
        "-t", str(props["duree"]), a.sortie])
    res = subprocess.run(["ffmpeg", "-v", "info", "-i", a.sortie, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr.split("Summary:")[-1]
    i = res.split("I:")[1].split("LUFS")[0].strip()
    pk = res.split("Peak:")[1].split("dBFS")[0].strip()
    print(f"▶ Vidéo finale : {a.sortie}  (volume {i} LUFS, crête {pk} dBTP)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="etape", required=True)
    p1 = sub.add_parser("apercus")
    p1.add_argument("video")
    p1.add_argument("effets")
    p1.add_argument("--musique")
    p2 = sub.add_parser("rendu")
    p2.add_argument("--sortie", default=os.path.join(OUT, "video_finale.mp4"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    apercus(a) if a.etape == "apercus" else rendu(a)


if __name__ == "__main__":
    main()
