#!/usr/bin/env python3
"""Prépare tout ce dont le moteur Remotion a besoin, à partir de :
  - la vidéo face caméra (déjà dérushée de préférence),
  - le fichier d'effets (effets.json, temps en secondes),
  - une musique facultative.

Produit public/media/*, public/sons/*.wav (générés avec ffmpeg) et props.json.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ICI, "public")
sys.path.insert(0, os.path.join(ICI, "..", "derush"))

# Orthographe imposée par le skill mon-style-signature (section « Mots à corriger »)
CORRECTIONS = [
    (r"\bd[ée]bor+ah?\b|\bv[ée]bora\b", "Déborah"),
    (r"\blipo[\s-]?cavitations?\b|\blipo-?camitation\b", "lipocavitation"),
    (r"\bradio[\s-]fr[ée]quence\b", "radiofréquence"),
    (r"\blipo[\s-]laser\b", "lipolaser"),
    (r"\bvac+u+m\b", "vacuum"),
    (r"\bmicro[\s-]?n[ei]+dling\b|\bmicroneelding\b", "microneedling"),
    (r"\bb\.?b\.?l\b", "BBL"),
]

# ----------------------------------------------------------------------------- sons (ffmpeg)
SONS = {
    # whoosh : souffle filtré qui monte puis retombe
    "whoosh": "aevalsrc='(random(0)*2-1)*pow(sin(PI*t/0.55),3)':s=48000:d=0.55,"
              "highpass=f=350,lowpass=f=2800,aphaser=decay=0.5:speed=1.6,volume=2.5",
    # montée : glissando doux + souffle, pour les accroches
    "montee": "aevalsrc='0.5*sin(2*PI*(220*t+700*t*t))*pow(t/0.9,2)*(1-pow(t/0.9,8))"
              "+0.2*(random(0)*2-1)*pow(t/0.9,3)':s=48000:d=0.9,lowpass=f=4000",
    # impact : basse sourde + petite attaque, pour les grands titres
    "impact": "aevalsrc='0.9*sin(2*PI*(70*t-30*t*t))*exp(-7*t)+0.35*(random(0)*2-1)*exp(-40*t)':s=48000:d=0.7,"
              "lowpass=f=1800",
    # scintillement : petites clochettes aiguës décalées
    "scintillement": "aevalsrc='0.35*(sin(2*PI*2637*t)*exp(-9*t)+sin(2*PI*3520*(t-0.07))*exp(-9*(t-0.07))*gte(t,0.07)"
                     "+sin(2*PI*4186*(t-0.14))*exp(-9*(t-0.14))*gte(t,0.14)"
                     "+sin(2*PI*5274*(t-0.21))*exp(-10*(t-0.21))*gte(t,0.21))':s=48000:d=0.8",
    # pop : petite bulle pour les icônes
    "pop": "aevalsrc='0.8*sin(2*PI*(900*t-2600*t*t))*exp(-22*t)':s=48000:d=0.25",
    # tic : clic de clavier / compteur
    "tic": "aevalsrc='0.6*(random(0)*2-1)*exp(-260*t)+0.3*sin(2*PI*1800*t)*exp(-120*t)':s=48000:d=0.05,"
           "highpass=f=1200",
}


def generer_sons(force=False):
    dossier = os.path.join(PUBLIC, "sons")
    os.makedirs(dossier, exist_ok=True)
    for nom, expr in SONS.items():
        out = os.path.join(dossier, f"{nom}.wav")
        if force or not os.path.exists(out):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", expr,
                            "-af", "afade=t=in:d=0.003,alimiter=limit=0.7", "-ac", "2", out],
                           check=True)


# ----------------------------------------------------------------------------- mesures
def sonde(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate,width,height:format=duration", "-of", "json", video],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    n, d = j["streams"][0]["r_frame_rate"].split("/")
    return float(n) / float(d), float(j["format"]["duration"]), j["streams"][0]["width"], j["streams"][0]["height"]


def lufs(fichier, debut=None, fin=None):
    cmd = ["ffmpeg", "-nostats", "-v", "info"]
    if debut is not None:
        cmd += ["-ss", str(debut), "-to", str(fin)]
    cmd += ["-i", fichier, "-af", "ebur128", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else None


def luminosite_centre(video):
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", video, "-vf",
                          "fps=1,crop=iw*0.8:ih*0.3:iw*0.1:ih*0.35,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    vals = [float(v) for v in re.findall(r"YAVG=([\d.]+)", err)]
    return sum(vals) / len(vals) if vals else 128.0


def corriger(mot):
    for motif, rempl in CORRECTIONS:
        mot = re.sub(motif, rempl, mot, flags=re.IGNORECASE)
    return mot


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("effets")
    ap.add_argument("--musique")
    ap.add_argument("--modele", default="medium")
    ap.add_argument("--transcription", help="réutiliser une transcription (json de mots) déjà faite")
    ap.add_argument("--props", default=os.path.join(ICI, "props.json"), help="fichier de sortie")
    args = ap.parse_args()

    effets = json.load(open(args.effets, encoding="utf-8"))
    fps, duree_video, w, h = sonde(args.video)
    os.makedirs(os.path.join(PUBLIC, "media"), exist_ok=True)
    shutil.copy(args.video, os.path.join(PUBLIC, "media", "video.mp4"))
    generer_sons()

    # 1. transcription mot à mot
    if args.transcription:
        mots = json.load(open(args.transcription, encoding="utf-8"))
        moteur, raison = "transcription fournie", args.transcription
    else:
        import derush
        tmp = os.path.join(PUBLIC, "media", "voix.wav")
        derush.extract_audio(args.video, tmp)
        moteur, raison, mots = derush.transcribe(tmp, args.modele, None)
        os.remove(tmp)
        with open(os.path.splitext(args.props)[0] + "_mots.json", "w", encoding="utf-8") as f:
            json.dump(mots, f, ensure_ascii=False)
    print(f"▶ Transcription : {moteur} ({raison})")
    # si le script est fourni, il sert d'orthographe de référence (les horaires restent ceux de la voix)
    if effets.get("script"):
        import derush
        sc = []
        for x in effets["script"].split():
            if sc and not norm(x):
                sc[-1] += " " + x  # ponctuation isolée (« pas ? ») : collée au mot précédent
            else:
                sc.append(x)
        pairs = derush.align([norm(x) for x in sc], [norm(m["mot"]) for m in mots], thr=0.5)
        for si, ti in pairs:
            if si is not None and ti is not None:
                mots[ti] = {**mots[ti], "mot": sc[si]}
    mots_cles = {norm(m) for m in effets.get("mots_cles", [])}
    legendes = []
    for m in mots:
        texte = corriger(m["mot"])
        legendes.append({"text": " " + texte, "startMs": round(m["debut"] * 1000), "endMs": round(m["fin"] * 1000),
                         "timestampMs": None, "confidence": None, "motCle": norm(texte) in mots_cles})
    print("  " + "".join(l["text"] for l in legendes))

    # 2. zones de parole (pour baisser la musique quand je parle)
    parole = []
    for m in mots:
        if parole and m["debut"] - parole[-1][1] < 0.35:
            parole[-1][1] = m["fin"]
        else:
            parole.append([m["debut"], m["fin"]])

    # 3. musique facultative : placée 20 dB sous la voix
    musique = None
    if args.musique:
        ext = os.path.splitext(args.musique)[1]
        shutil.copy(args.musique, os.path.join(PUBLIC, "media", "musique" + ext))
        l_voix = lufs(args.video)
        l_mus = lufs(args.musique)
        gain_db = (l_voix - 20.0) - l_mus
        musique = {"src": "media/musique" + ext, "gainDb": round(gain_db, 2),
                   "voixLufs": l_voix, "musiqueLufs": l_mus}
        print(f"▶ Musique : voix {l_voix} LUFS, musique {l_mus} LUFS -> gain {gain_db:+.1f} dB (20 dB sous la voix)")

    lum = luminosite_centre(args.video)
    props = {
        "video": "media/video.mp4", "fps": fps, "duree": float(effets.get("duree", duree_video)),
        "largeur": 1080, "hauteur": 1920,
        "fondClair": lum > 150 if effets.get("fond", "auto") == "auto" else effets["fond"] == "clair",
        "legendes": legendes, "parole": parole, "musique": musique,
        "coupes": effets.get("coupes", []), "chapitres": effets.get("chapitres", []),
        "effets": effets.get("effets", []), "ambiance": effets.get("ambiance", {}),
        "moteurTranscription": moteur,
    }
    with open(args.props, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=1)
    print(f"▶ props.json écrit ({len(legendes)} mots, {len(props['effets'])} effets, "
          f"fond {'clair' if props['fondClair'] else 'sombre'} : luminosité {lum:.0f}/255)")


if __name__ == "__main__":
    main()
