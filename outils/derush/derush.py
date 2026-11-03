#!/usr/bin/env python3
"""Dérush automatique pour vidéos face caméra.

Usage :
    python3 derush.py MA_VIDEO.mp4 --script MON_SCRIPT.txt [--sortie video_derushee.mp4]

Étapes :
  1. Transcription mot par mot (ElevenLabs Scribe scribe_v1 si clé + crédit, sinon Whisper local).
  2. Alignement mot à mot avec le script : les mots en trop (reprises, hésitations) sont repérés,
     et quand une phrase est répétée, c'est la DERNIÈRE prise qui est gardée.
  3. Chaque coupe tombe dans un silence, avec un seuil calibré sur le fichier lui-même.
  4. Les coupes sont calées sur les images de la vidéo (son et image restent synchronisés).
  5. Vérifications : niveau sonore à chaque raccord, puis retranscription de la vidéo coupée
     et comparaison mot à mot. Si un mot manque, la coupe est corrigée avant livraison.
"""
import argparse
import difflib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

import numpy as np
from scipy.io import wavfile

SR = 16000
FRAME = 0.020          # fenêtre d'analyse du son (20 ms)
HOP = 0.010            # pas d'analyse (10 ms)
MIN_SILENCE = 0.060    # un silence doit durer au moins 60 ms pour accueillir une coupe
EDGE_MARGIN = 0.020    # marge de sécurité à l'intérieur d'un silence
HESITATIONS = {"euh", "heu", "euhm", "hum", "hmm", "mmh", "mm", "bah", "ben", "ah", "oh", "eh", "hein"}


# ----------------------------------------------------------------------------- outils
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Commande échouée : {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout


def probe(video):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=r_frame_rate:format=duration", "-of", "json", video])
    info = json.loads(out)
    num, den = info["streams"][0]["r_frame_rate"].split("/")
    return float(num) / float(den), float(info["format"]["duration"])


def extract_audio(video, wav):
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(SR),
         "-c:a", "pcm_s16le", wav])
    sr, data = wavfile.read(wav)
    return data.astype(np.float32) / 32768.0


def norm(word):
    w = unicodedata.normalize("NFD", word.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def tokenize_script(text):
    return [n for n in (norm(t) for t in text.split()) if n]


def similar(a, b):
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ----------------------------------------------------------------------------- 1. transcription
def eleven_key():
    key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not key:
        p = os.path.expanduser("~/.elevenlabs_key")
        if os.path.exists(p):
            key = open(p).read().strip()
    return key or None


def transcribe_elevenlabs(wav, key):
    import requests
    h = {"xi-api-key": key}
    sub = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=h, timeout=30)
    sub.raise_for_status()
    s = sub.json()
    remaining = s.get("character_limit", 0) - s.get("character_count", 0)
    if remaining <= 0:
        raise RuntimeError("plus de crédit ElevenLabs")
    with open(wav, "rb") as f:
        r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers=h, timeout=600,
                          data={"model_id": "scribe_v1", "language_code": "fra",
                                "timestamps_granularity": "word", "tag_audio_events": "false"},
                          files={"file": ("audio.wav", f, "audio/wav")})
    r.raise_for_status()
    return [{"mot": w["text"].strip(), "debut": float(w["start"]), "fin": float(w["end"])}
            for w in r.json().get("words", []) if w.get("type", "word") == "word" and w["text"].strip()]


_WHISPER = {}


def transcribe_whisper(wav, model_name):
    import whisper
    if model_name not in _WHISPER:
        _WHISPER[model_name] = whisper.load_model(model_name)
    res = _WHISPER[model_name].transcribe(
        wav, language="fr", word_timestamps=True, temperature=0.0,
        condition_on_previous_text=False, fp16=False,
        # incite Whisper à écrire les hésitations au lieu de les effacer
        initial_prompt="Euh, alors, hum... je, je veux dire, euh, bon.")
    words = []
    for seg in res["segments"]:
        for w in seg.get("words", []):
            t = w["word"].strip()
            if t:
                words.append({"mot": t, "debut": float(w["start"]), "fin": float(w["end"])})
    return words


def merge_pieces(words):
    """Recolle les morceaux que Whisper sépare : « m » + « 'appelle », « lipo » + « -cavitation »."""
    out = []
    for w in words:
        t = w["mot"]
        if out and (t[:1] in "'’-" or out[-1]["mot"][-1:] in "'’-"):
            out[-1] = {"mot": out[-1]["mot"] + t, "debut": out[-1]["debut"], "fin": w["fin"]}
        else:
            out.append(dict(w))
    return out


def transcribe(wav, model_name, forced=None):
    """Renvoie (moteur utilisé, raison, mots)."""
    if forced != "whisper":
        key = eleven_key()
        if not key:
            reason = "pas de clé ElevenLabs trouvée"
        else:
            try:
                return "ElevenLabs Scribe (scribe_v1)", "clé présente et crédit disponible", \
                    merge_pieces(transcribe_elevenlabs(wav, key))
            except Exception as e:  # pas de crédit, réseau, clé invalide...
                reason = f"ElevenLabs indisponible ({str(e)[:120]})"
    else:
        reason = "Whisper forcé"
    return f"Whisper local ({model_name})", reason, merge_pieces(transcribe_whisper(wav, model_name))


# ----------------------------------------------------------------------------- 2. alignement
def align(a, b, thr=0.75):
    """Alignement mot à mot (Needleman-Wunsch). Renvoie une liste de paires (i, j), None = trou.
    En cas d'égalité, la remontée depuis la fin préfère les correspondances les plus tardives :
    quand une phrase est répétée, c'est la dernière prise qui est associée au script."""
    n, m = len(a), len(b)
    MATCH, SUB, GAP = 2.0, -1.0, -1.0
    sc = np.zeros((n + 1, m + 1))
    sc[:, 0] = np.arange(n + 1) * GAP
    sc[0, :] = np.arange(m + 1) * GAP
    sim = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            sim[i, j] = similar(a[i], b[j])
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = MATCH if sim[i - 1, j - 1] >= thr else SUB
            sc[i, j] = max(sc[i - 1, j - 1] + d, sc[i - 1, j] + GAP, sc[i, j - 1] + GAP)
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            d = MATCH if sim[i - 1, j - 1] >= thr else SUB
            if sc[i, j] == sc[i - 1, j - 1] + d:
                pairs.append((i - 1, j - 1)); i -= 1; j -= 1; continue
        if j > 0 and sc[i, j] == sc[i, j - 1] + GAP:
            pairs.append((None, j - 1)); j -= 1; continue
        pairs.append((i - 1, None)); i -= 1
    return pairs[::-1]


def same_word(a, b):
    return similar(a, b) >= 0.75 or (len(a) >= 3 and b.startswith(a)) or (len(b) >= 3 and a.startswith(b))


def false_starts(sp, script):
    """Repère les phrases recommencées : « A B C ... A B C D » -> la première prise « A B C » est une reprise.
    Ignore les répétitions qui sont écrites telles quelles dans le script (« très très »)."""
    marks = set()
    script_txt = " " + " ".join(script) + " "
    t = 0
    while t < len(sp):
        found = 0
        for k in range(1, 13):                # longueur de la prise ratée (en mots), la plus courte d'abord
            if t + k >= len(sp):
                continue
            body = [x for x in sp[t:t + k] if x not in HESITATIONS]
            if not body:
                continue
            need = min(len(body), 3)
            nxt = [x for x in sp[t + k:t + k + need + 2] if x not in HESITATIONS][:need]
            if len(nxt) == need and all(same_word(body[q], nxt[q]) for q in range(need)):
                gram = " " + " ".join(nxt) + " "
                if (" " + " ".join(body + body) + " ") in script_txt or script_txt.count(gram) >= 2:
                    continue              # la répétition est voulue : elle est dans le script
                found = k
                break
        if found:
            marks.update(range(t, t + found))
            t += found
        else:
            t += 1
    return marks


def classify(script, spoken, cut_additions=False):
    """Décide pour chaque mot prononcé s'il est gardé ou coupé (reprise / hésitation)."""
    sp = [norm(w["mot"]) for w in spoken]
    pairs = align(script, sp)
    status = ["garde"] * len(sp)
    script_pos = [None] * len(sp)
    for si, ti in pairs:
        if ti is not None:
            script_pos[ti] = si
            if si is None:
                status[ti] = "en_trop"
    # Qualifier chaque groupe de mots en trop
    k = 0
    while k < len(sp):
        if status[k] != "en_trop":
            k += 1; continue
        e = k
        while e + 1 < len(sp) and status[e + 1] == "en_trop":
            e += 1
        nxt = next((script_pos[x] for x in range(e + 1, len(sp)) if script_pos[x] is not None), len(script))
        prv = next((script_pos[x] for x in range(k - 1, -1, -1) if script_pos[x] is not None), -1)
        window = script[max(0, prv - 2): nxt + (e - k) + 4]
        for x in range(k, e + 1):
            w = sp[x]
            if w in HESITATIONS:
                status[x] = "hesitation"
            elif any(same_word(w, s) for s in window):
                status[x] = "reprise"
            else:
                status[x] = "reprise" if cut_additions else "ajout_garde"
        k = e + 1
    # Phrases recommencées : on garde toujours la DERNIÈRE prise
    for x in false_starts(sp, script):
        if status[x] != "hesitation":
            status[x] = "reprise"
    return status


# ----------------------------------------------------------------------------- 3. silences
def energy_db(audio):
    fl, hp = int(FRAME * SR), int(HOP * SR)
    nfr = max(1, 1 + (len(audio) - fl) // hp)
    idx = np.arange(fl)[None, :] + hp * np.arange(nfr)[:, None]
    frames = audio[np.clip(idx, 0, len(audio) - 1)]
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-9)


def frame_time(k):
    return k * HOP + FRAME / 2


def calibrate(db, words):
    """Seuil de silence calibré sur CE fichier : entre le bruit de fond et la voix."""
    floor = float(np.percentile(db, 10))
    in_words = np.zeros(len(db), bool)
    for w in words:
        a, b = int(w["debut"] / HOP), int(w["fin"] / HOP) + 1
        in_words[max(0, a):min(len(db), b)] = True
    voice = float(np.percentile(db[in_words], 90)) if in_words.any() else float(np.percentile(db, 95))
    thr = floor + max(6.0, 0.25 * (voice - floor))
    return {"bruit_de_fond_db": round(floor, 1), "voix_db": round(voice, 1), "seuil_silence_db": round(thr, 1)}


def silent_runs(db, thr):
    sil = db < thr
    runs, k = [], 0
    while k < len(sil):
        if sil[k]:
            e = k
            while e + 1 < len(sil) and sil[e + 1]:
                e += 1
            t0, t1 = k * HOP, e * HOP + FRAME
            if t1 - t0 >= MIN_SILENCE:
                runs.append((t0, t1))
            k = e + 1
        else:
            k += 1
    return runs


def level_max(db, t0, t1):
    a, b = max(0, int(t0 / HOP)), min(len(db), int(math.ceil(t1 / HOP)) + 1)
    return float(db[a:b].max()) if b > a else -120.0


def snap_in_run(target, run_, fps):
    """Cale un instant sur une image de la vidéo, en restant dans le silence."""
    lo, hi = run_[0] + EDGE_MARGIN, run_[1] - EDGE_MARGIN
    k0, k1 = math.ceil(lo * fps), math.floor(hi * fps)
    if k1 < k0:
        return None
    k = min(max(round(target * fps), k0), k1)
    return k / fps


def find_run(runs, lo, hi):
    """Le silence le plus long situé entre deux instants (les horaires de Whisper sont approximatifs)."""
    best, best_len = None, 0.0
    for r in runs:
        a, b = max(r[0], lo), min(r[1], hi)
        if b - a > best_len:
            best, best_len = (a, b), b - a
    return best


def plan_cuts(words, status, runs, fps, duration):
    cuts, refused = [], []
    n, k = len(words), 0
    mid = lambda w: (w["debut"] + w["fin"]) / 2
    while k < n:
        if status[k] not in ("reprise", "hesitation"):
            k += 1; continue
        e = k
        while e + 1 < n and status[e + 1] in ("reprise", "hesitation"):
            e += 1
        group = [words[x]["mot"] for x in range(k, e + 1)]
        # début de la coupe : dans le silence entre le dernier mot gardé et le premier mot coupé
        if k == 0:
            cs, rs = 0.0, (0.0, 0.0)
        else:
            p = words[k - 1]
            rs = find_run(runs, p["debut"], words[k]["fin"])
            cs = None if rs is None else snap_in_run(rs[0] + min(0.10, 0.4 * (rs[1] - rs[0])), rs, fps)
        # fin de la coupe : dans le silence entre le dernier mot coupé et le mot gardé suivant
        if e == n - 1:
            ce, re_ = math.floor(duration * fps) / fps, (duration, duration)
        else:
            q = words[e + 1]
            re_ = find_run(runs, words[e]["debut"], q["fin"])
            ce = None if re_ is None else snap_in_run(re_[1] - min(0.10, 0.4 * (re_[1] - re_[0])), re_, fps)
        if cs is None or ce is None or ce - cs < 1.0 / fps:
            refused.append({"mots": group, "raison": "pas de silence assez long autour : non coupé par sécurité"})
        else:
            cuts.append({"debut": cs, "fin": ce, "mots": group, "silence_debut": rs, "silence_fin": re_})
        k = e + 1
    cuts.sort(key=lambda c: c["debut"])
    return cuts, refused


def keep_segments(cuts, duration, fps):
    segs, t = [], 0.0
    for c in cuts:
        if c["debut"] > t:
            segs.append((t, c["debut"]))
        t = max(t, c["fin"])
    end = math.floor(duration * fps) / fps
    if end > t:
        segs.append((t, end))
    return [s for s in segs if s[1] - s[0] >= 1.0 / fps]


def render(video, segs, out):
    parts, labels = [], ""
    for i, (a, b) in enumerate(segs):
        d = b - a
        fade = min(0.005, d / 4)
        parts.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade:.4f},afade=t=out:st={max(0, d - fade):.4f}:d={fade:.4f}[a{i}]")
        labels += f"[v{i}][a{i}]"
    parts.append(f"{labels}concat=n={len(segs)}:v=1:a=1[v][a]")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(";\n".join(parts))
        script = f.name
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-filter_complex_script", script,
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out])
    os.unlink(script)


def to_output_time(t, cuts):
    return t - sum(max(0.0, min(c["fin"], t) - c["debut"]) for c in cuts if c["debut"] < t)


# ----------------------------------------------------------------------------- 5. vérifications
def verify(video_in, video_out, words, status, cuts, db, thr, engine_args, tmp):
    rep = {"raccords": [], "mots_manquants": [], "mots_coupes_par_erreur": []}
    # a) son à chaque raccord : juste avant et juste après chaque coupe, dans l'original et la sortie
    out_audio = extract_audio(video_out, os.path.join(tmp, "sortie.wav"))
    db_out = energy_db(out_audio)
    for c in cuts:
        before = level_max(db, c["debut"] - 0.03, c["debut"])
        after = level_max(db, c["fin"], c["fin"] + 0.03)
        t_out = to_output_time(c["debut"], cuts)
        at_join = level_max(db_out, t_out - 0.03, t_out + 0.03)
        ok = before < thr and after < thr and at_join < thr
        rep["raccords"].append({"coupe": f"{c['debut']:.3f}s -> {c['fin']:.3f}s", "mots_retires": " ".join(c["mots"]),
                                "son_avant_db": round(before, 1), "son_apres_db": round(after, 1),
                                "son_au_raccord_sortie_db": round(at_join, 1), "seuil_db": round(thr, 1),
                                "ok": bool(ok)})
    # b) aucun mot gardé ne chevauche une coupe (contrôle par le calcul)
    for idx, (w, s) in enumerate(zip(words, status)):
        if s in ("reprise", "hesitation"):
            continue
        for c in cuts:
            if w["debut"] + 0.05 < c["fin"] and w["fin"] - 0.05 > c["debut"]:
                rep["mots_coupes_par_erreur"].append({"index": idx, "mot": w["mot"], "debut": w["debut"]})
    # c) retranscription de la vidéo coupée et comparaison mot à mot
    engine, _, out_words = transcribe(os.path.join(tmp, "sortie.wav"), *engine_args)
    rep["moteur_retranscription"] = engine
    expected = [(i, w) for i, (w, s) in enumerate(zip(words, status)) if s not in ("reprise", "hesitation")]
    pairs = align([norm(w["mot"]) for _, w in expected], [norm(w["mot"]) for w in out_words], thr=0.6)
    for ei, oi in pairs:
        if ei is not None and oi is None:
            idx, w = expected[ei]
            inside_cut = any(w["debut"] + 0.02 < c["fin"] and w["fin"] - 0.02 > c["debut"] for c in cuts)
            t0, t1 = to_output_time(w["debut"], cuts), to_output_time(w["fin"], cuts)
            sound = level_max(db_out, t0, t1)
            rep["mots_manquants"].append({"index": idx, "mot": w["mot"], "debut": w["debut"],
                                          "dans_une_coupe": inside_cut, "son_dans_la_sortie_db": round(sound, 1),
                                          "son_present": bool(sound >= thr)})
    rep["texte_sortie"] = " ".join(w["mot"] for w in out_words)
    return rep


def fix_cuts(cuts, missing_idx, words, runs, fps):
    """Rétrécit (ou annule) la coupe qui a avalé un mot à garder."""
    changed = False
    for idx in missing_idx:
        w = words[idx]
        for c in list(cuts):
            if not (w["debut"] < c["fin"] and w["fin"] > c["debut"]):
                continue
            changed = True
            if (w["debut"] + w["fin"]) / 2 - c["debut"] < c["fin"] - (w["debut"] + w["fin"]) / 2:
                r = find_run(runs, w["fin"], w["fin"] + 0.6)
                t = snap_in_run(r[0] + 0.05, r, fps) if r else None
                if t is None or t >= c["fin"]:
                    cuts.remove(c)
                else:
                    c["debut"] = t
            else:
                r = find_run(runs, w["debut"] - 0.6, w["debut"])
                t = snap_in_run(r[1] - 0.05, r, fps) if r else None
                if t is None or t <= c["debut"]:
                    cuts.remove(c)
                else:
                    c["fin"] = t
    return changed


# ----------------------------------------------------------------------------- programme principal
def main():
    ap = argparse.ArgumentParser(description="Dérush automatique de vidéos face caméra")
    ap.add_argument("video")
    ap.add_argument("--script", required=True, help="fichier texte du script prévu")
    ap.add_argument("--sortie", help="vidéo dérushée (par défaut : NOM_derush.mp4)")
    ap.add_argument("--modele", default="medium", help="modèle Whisper (medium, turbo, large-v3...)")
    ap.add_argument("--moteur", choices=["auto", "whisper"], default="auto")
    ap.add_argument("--couper-ajouts", action="store_true",
                    help="couper aussi les mots ajoutés hors script qui ne sont pas des reprises")
    args = ap.parse_args()

    out = args.sortie or os.path.splitext(args.video)[0] + "_derush.mp4"
    script = tokenize_script(open(args.script, encoding="utf-8").read())
    fps, duration = probe(args.video)
    tmp = tempfile.mkdtemp(prefix="derush_")
    engine_args = (args.modele, "whisper" if args.moteur == "whisper" else None)

    print(f"▶ Vidéo : {args.video} ({duration:.2f} s, {fps:g} images/s)")
    audio = extract_audio(args.video, os.path.join(tmp, "original.wav"))
    engine, reason, words = transcribe(os.path.join(tmp, "original.wav"), *engine_args)
    print(f"▶ Transcription : {engine} ({reason})")
    print("  Entendu : " + " ".join(w["mot"] for w in words))

    status = classify(script, words, args.couper_ajouts)
    db = energy_db(audio)
    calib = calibrate(db, words)
    thr = calib["seuil_silence_db"]
    runs = silent_runs(db, thr)
    print(f"▶ Calibrage du silence : bruit de fond {calib['bruit_de_fond_db']} dB, voix {calib['voix_db']} dB "
          f"-> seuil {thr} dB")

    cuts, refused = plan_cuts(words, status, runs, fps, duration)
    report = {"video": args.video, "sortie": out, "moteur_transcription": engine, "raison_moteur": reason,
              "images_par_seconde": fps, "calibrage": calib,
              "mots": [{**w, "decision": s} for w, s in zip(words, status)], "coupes_refusees": refused}

    for attempt in range(1, 4):
        segs = keep_segments(cuts, duration, fps)
        render(args.video, segs, out)
        ver = verify(args.video, out, words, status, cuts, db, thr, engine_args, tmp)
        really_missing = [m["index"] for m in ver["mots_manquants"] if m["dans_une_coupe"] or not m["son_present"]]
        really_missing += [e["index"] for e in ver["mots_coupes_par_erreur"]]
        report.setdefault("passes", []).append({"passe": attempt, "nb_coupes": len(cuts), "verification": ver})
        if not really_missing:
            break
        print(f"⚠ Passe {attempt} : {len(really_missing)} mot(s) touché(s), correction des coupes...")
        if not fix_cuts(cuts, sorted(set(really_missing)), words, runs, fps):
            break

    ver = report["passes"][-1]["verification"]
    frame_ok = all(abs(c["debut"] * fps - round(c["debut"] * fps)) < 1e-6 and
                   abs(c["fin"] * fps - round(c["fin"] * fps)) < 1e-6 for c in cuts)
    joins_ok = all(r["ok"] for r in ver["raccords"])
    lost = [m for m in ver["mots_manquants"] if m["dans_une_coupe"] or not m["son_present"]]
    report["coupes_finales"] = [{"debut": c["debut"], "fin": c["fin"], "mots": c["mots"],
                                 "image_debut": round(c["debut"] * fps), "image_fin": round(c["fin"] * fps)}
                                for c in cuts]
    report["bilan"] = {"coupes_sur_images": frame_ok, "raccords_dans_le_silence": joins_ok,
                       "mots_perdus": len(lost) + len(ver["mots_coupes_par_erreur"]),
                       "duree_avant": round(duration, 2),
                       "duree_apres": round(sum(b - a for a, b in keep_segments(cuts, duration, fps)), 2)}
    with open(os.path.splitext(out)[0] + "_rapport.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"▶ Décisions mot par mot :")
    for w, s in zip(words, status):
        print(f"   {w['debut']:6.2f}s  {w['mot']:<18} {s}")
    print(f"▶ Coupes ({len(cuts)}) :")
    for c in report["coupes_finales"]:
        print(f"   {c['debut']:.3f}s -> {c['fin']:.3f}s  (images {c['image_debut']} -> {c['image_fin']})  "
              f"retiré : {' '.join(c['mots'])}")
    for r in refused:
        print(f"   NON COUPÉ : {' '.join(r['mots'])} ({r['raison']})")
    for p_ in report["passes"]:
        v = p_["verification"]
        n_lost = sum(1 for m in v["mots_manquants"] if m["dans_une_coupe"] or not m["son_present"]) \
            + len(v["mots_coupes_par_erreur"])
        print(f"   passe {p_['passe']} : {p_['nb_coupes']} coupe(s), mots touchés : {n_lost}"
              + ("  -> coupes corrigées" if n_lost else "  -> rien de perdu"))
    print("▶ Vérifications (passe finale) :")
    for r in ver["raccords"]:
        print(f"   raccord {r['coupe']} : avant {r['son_avant_db']} dB, après {r['son_apres_db']} dB, "
              f"dans la sortie {r['son_au_raccord_sortie_db']} dB (seuil {r['seuil_db']}) -> "
              f"{'OK' if r['ok'] else 'PROBLÈME'}")
    print(f"   Retranscription de la vidéo coupée ({ver['moteur_retranscription']}) : {ver['texte_sortie']}")
    for m in ver["mots_manquants"]:
        verdict = "PERDU" if (m["dans_une_coupe"] or not m["son_present"]) else \
            f"non réécrit par la transcription mais bien présent dans le son ({m['son_dans_la_sortie_db']} dB)"
        print(f"   mot « {m['mot']} » : {verdict}")
    b = report["bilan"]
    print(f"▶ BILAN : coupes calées sur les images : {'OUI' if b['coupes_sur_images'] else 'NON'} | "
          f"raccords dans le silence : {'OUI' if b['raccords_dans_le_silence'] else 'NON'} | "
          f"mots perdus : {b['mots_perdus']} | durée {b['duree_avant']} s -> {b['duree_apres']} s")
    print(f"▶ Vidéo livrée : {out}")
    return 0 if (b["mots_perdus"] == 0 and joins_ok and frame_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
