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
import shutil
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
EDGE_MARGIN = 0.045    # marge de sécurité à l'intérieur d'un silence
HESITATIONS = {"euh", "heu", "euhm", "hum", "hmm", "mmh", "mm", "bah", "ben", "ah", "oh", "eh", "hein", "tch", "pff"}
# élans faits uniquement de ces mots (« Non. », « Bon. ») : petites réactions entre deux prises
REACTIONS = {"non", "bon", "voila", "ok", "okay", "attends", "allez", "alors"}
# mots qui signalent une prise ratée : tout le groupe de mots en trop qui les contient est coupé
RECOMMENCE = {"recommence", "recommencer", "recommencé", "attends", "pardon", "oups", "zut", "mince"}


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


HALLUCINATIONS = re.compile(r"merci d.avoir regard|sous-titr|abonnez-vous|amara\.org|merci de votre attention", re.I)


def speech_chunks(audio):
    """Découpe le son en passages parlés séparés par des silences (Whisper rate les reprises sur un long fichier)."""
    db = energy_db(audio)
    floor, voice = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    active = db > floor + max(6.0, 0.25 * (voice - floor))
    regions, k = [], 0
    while k < len(active):
        if active[k]:
            e = k
            while e + 1 < len(active) and active[e + 1]:
                e += 1
            t0, t1 = k * HOP, e * HOP + FRAME
            if regions and t0 - regions[-1][1] < 0.6:
                regions[-1][1] = t1
            else:
                regions.append([t0, t1])
            k = e + 1
        else:
            k += 1
    regions = [r for r in regions if r[1] - r[0] >= 0.15]
    dur = len(audio) / SR
    chunks = []
    for i, (t0, t1) in enumerate(regions):
        lo = max(t0 - 0.3, (regions[i - 1][1] + t0) / 2 if i else 0.0)
        hi = min(t1 + 0.3, (t1 + regions[i + 1][0]) / 2 if i + 1 < len(regions) else dur)
        chunks.append((lo, hi))
    return chunks


def transcribe_whisper(wav, model_name):
    import whisper
    if model_name not in _WHISPER:
        _WHISPER[model_name] = whisper.load_model(model_name)
    sr, data = wavfile.read(wav)
    audio = data.astype(np.float32) / 32768.0
    words = []
    for lo, hi in speech_chunks(audio):
        clip = audio[int(lo * SR):int(hi * SR)]
        if len(clip) < SR * 0.2:
            continue
        res = _WHISPER[model_name].transcribe(
            clip, language="fr", word_timestamps=True, temperature=0.0,
            condition_on_previous_text=False, fp16=False,
            # incite Whisper à écrire les hésitations au lieu de les effacer
            initial_prompt="Euh, alors, hum... je, je veux dire, euh, bon.")
        for seg in res["segments"]:
            if HALLUCINATIONS.search(seg.get("text", "")):
                continue  # phrase inventée par Whisper sur un bruit ou un silence
            for w in seg.get("words", []):
                t = w["word"].strip()
                if t and t not in ("...", "…"):
                    words.append({"mot": t, "debut": round(lo + float(w["start"]), 3),
                                  "fin": round(lo + float(w["end"]), 3)})
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
    # une substitution coûte plus cher que deux trous : on n'associe que des mots vraiment identiques,
    # ce qui empêche de recoller des morceaux de prises différentes
    MATCH, SUB, GAP = 2.0, -3.0, -1.0
    sc = np.zeros((n + 1, m + 1))
    sc[:, 0] = np.arange(n + 1) * GAP
    sc[0, :] = np.arange(m + 1) * GAP
    sim = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            # mots courts (« pas », « repas ») : il faut qu'ils soient identiques
            sim[i, j] = 1.0 if a[i] == b[j] else (similar(a[i], b[j]) if min(len(a[i]), len(b[j])) >= 5 else 0.0)
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
        # à égalité, on saute plutôt un mot du script qu'un mot prononcé : le mot prononcé le plus tardif
        # reste candidat, donc c'est la DERNIÈRE prise qui est associée au script
        if i > 0 and sc[i, j] == sc[i - 1, j] + GAP:
            pairs.append((i - 1, None)); i -= 1; continue
        pairs.append((None, j - 1)); j -= 1
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


def script_sentences(text):
    """Phrases du script (les numéros de liste « 1. » restent collés à leur phrase)."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", text.strip()) if p.strip()]
    out = []
    for p in parts:
        if out and re.fullmatch(r"\d+[.)]?", out[-1]):
            out[-1] += " " + p
        else:
            out.append(p)
    return [w for w in ([n for n in (norm(t) for t in p.split()) if n and not n.isdigit()] for p in out) if w]


def lcs(a, b):
    """Nombre de mots en commun dans le même ordre."""
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a)):
        for j in range(len(b)):
            m[i + 1][j + 1] = m[i][j] + 1 if same_word(a[i], b[j]) else max(m[i][j + 1], m[i + 1][j])
    return m[-1][-1]


def classify(script_text, spoken, cut_additions=False):
    """Décide pour chaque mot prononcé s'il est gardé ou coupé, phrase par phrase :
    pour chaque phrase du script, on garde la DERNIÈRE prise complète, les autres sont des reprises."""
    sentences = script_sentences(script_text)
    sp = [norm(w["mot"]) for w in spoken]
    n = len(sp)
    # 1. élans de parole : séparés par une pause ou une ponctuation de fin
    phrases, cur = [], []
    for i, w in enumerate(spoken):
        if cur and (w["debut"] - spoken[i - 1]["fin"] > 0.45 or re.search(r"[.!?…]$", spoken[i - 1]["mot"])):
            phrases.append(cur)
            cur = []
        cur.append(i)
    if cur:
        phrases.append(cur)
    words_of = lambda a, b: [x for ph in phrases[a:b + 1] for x in ph if sp[x] not in HESITATIONS]

    # 2. pour chaque phrase du script (de la fin vers le début), la dernière prise qui la dit en entier
    chosen = {}
    limit = len(phrases)
    for si in range(len(sentences) - 1, -1, -1):
        target = sentences[si]
        best = None
        for a in range(limit - 1, -1, -1):
            for b in range(a, min(a + 3, limit)):
                ws = [sp[x] for x in words_of(a, b)]
                if not ws:
                    continue
                common = lcs(target, ws)
                rappel, precision = common / len(target), common / len(ws)
                if rappel >= 0.75 and precision >= 0.6:
                    score = (rappel + precision, -(b - a))
                    if best is None or score > best[0]:
                        best = (score, a, b)
            if best:
                break  # la prise la plus tardive qui convient
        if best:
            _, a, b = best
            chosen[si] = (a, b)
            limit = a

    status = ["reprise"] * n
    kept_phrases = {p for a, b in chosen.values() for p in range(a, b + 1)}
    for pi, ph in enumerate(phrases):
        ws = [sp[x] for x in ph]
        if pi in kept_phrases:
            for x in ph:
                status[x] = "hesitation" if sp[x] in HESITATIONS else "garde"
            continue
        if any(w in {norm(r) for r in RECOMMENCE} for w in ws) or all(w in REACTIONS | HESITATIONS for w in ws):
            for x in ph:
                status[x] = "hesitation"
            continue
        # élan qui ne correspond à aucune prise gardée : essai raté d'une phrase du script, ou ajout
        ressemble = any(lcs(t, ws) / max(1, len(ws)) >= 0.5 for t in sentences)
        for x in ph:
            if sp[x] in HESITATIONS:
                status[x] = "hesitation"
            elif ressemble or cut_additions:
                status[x] = "reprise"
            else:
                status[x] = "ajout_garde"

    # 3. dans une prise gardée, les débuts de phrase recommencés (« faire du renfor... faire du renforcement »)
    for a, b in chosen.values():
        idx = [x for p in range(a, b + 1) for x in phrases[p]]
        local = false_starts([sp[x] for x in idx], [w for t in sentences for w in t])
        for k in local:
            if status[idx[k]] == "garde":
                status[idx[k]] = "reprise"
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
    # repli : une respiration entre deux prises, au moins 24 dB sous la voix
    pause = max(thr, voice - 24.0)
    return {"bruit_de_fond_db": round(floor, 1), "voix_db": round(voice, 1), "seuil_silence_db": round(thr, 1),
            "seuil_respiration_db": round(pause, 1)}


def breath_runs(db, pause_thr, words):
    """Respirations utilisables pour une coupe : sous le seuil de respiration, au moins 0,12 s,
    et sans toucher le cœur d'un mot transcrit (le milieu de chaque mot reste protégé)."""
    cores = [(w["debut"] + 0.3 * (w["fin"] - w["debut"]), w["fin"] - 0.3 * (w["fin"] - w["debut"])) for w in words]
    out = []
    for r in silent_runs(db, pause_thr):
        if r[1] - r[0] < 0.12:
            continue
        if any(a < r[1] and b > r[0] for a, b in cores):
            continue
        out.append(r)
    return out


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


def plan_cuts(words, status, runs, fps, duration, breaths=(), pause_max=0.5):
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
        seuil_debut = seuil_fin = "silence"
        # début de la coupe : dans le silence entre le dernier mot gardé et le premier mot coupé
        if k == 0:
            cs, rs = 0.0, (0.0, 0.0)
        else:
            p = words[k - 1]
            rs = find_run(runs, p["debut"], words[k]["fin"])
            cs = None if rs is None else snap_in_run(rs[0] + min(0.10, 0.4 * (rs[1] - rs[0])), rs, fps)
            if cs is None:  # pas de silence : une respiration entre le mot gardé et la reprise
                rs = find_run(breaths, p["debut"], words[k]["fin"])
                cs = None if rs is None else snap_in_run((rs[0] + rs[1]) / 2, rs, fps)
                seuil_debut = "respiration" if cs is not None else seuil_debut
        # fin de la coupe : dans le silence entre le dernier mot coupé et le mot gardé suivant
        if e == n - 1:
            ce, re_ = math.floor(duration * fps) / fps, (duration, duration)
        else:
            q = words[e + 1]
            re_ = find_run(runs, words[e]["debut"], q["fin"])
            ce = None if re_ is None else snap_in_run(re_[1] - min(0.10, 0.4 * (re_[1] - re_[0])), re_, fps)
            if ce is None:
                re_ = find_run(breaths, words[e]["debut"], q["fin"])
                ce = None if re_ is None else snap_in_run((re_[0] + re_[1]) / 2, re_, fps)
                seuil_fin = "respiration" if ce is not None else seuil_fin
        partiel = False
        # pas de silence au bord : on coupe quand même ce qui peut l'être, d'un silence à l'autre à l'intérieur du groupe
        interieurs = [r for r in runs if r[0] > words[k]["debut"] and r[1] < words[e]["fin"] and r[1] - r[0] >= MIN_SILENCE]
        if cs is None and interieurs:
            r = interieurs[0]
            cs, partiel = snap_in_run(r[0] + min(0.10, 0.4 * (r[1] - r[0])), r, fps), True
        if ce is None and interieurs:
            r = interieurs[-1]
            ce, partiel = snap_in_run(r[1] - min(0.10, 0.4 * (r[1] - r[0])), r, fps), True
        if cs is None or ce is None or ce - cs < 1.0 / fps:
            refused.append({"mots": group, "raison": "pas de silence assez long autour : non coupé par sécurité"})
        else:
            cuts.append({"debut": cs, "fin": ce, "mots": group, "silence_debut": rs, "silence_fin": re_,
                         "seuil_debut": seuil_debut, "seuil_fin": seuil_fin})
            if partiel:
                refused.append({"mots": group, "raison": "coupé en partie seulement : pas de silence entre la reprise "
                                                          "et la phrase gardée, un bout de reprise reste"})
        k = e + 1
    # début et fin : on enlève l'attente avant le premier mot gardé et après le dernier
    gardes = [i for i, st in enumerate(status) if st not in ("reprise", "hesitation")]
    if gardes:
        premier, dernier = words[gardes[0]], words[gardes[-1]]
        r = find_run(runs, max(0.0, premier["debut"] - 3.0), premier["debut"] + 0.15)
        t = snap_in_run(r[1] - 0.25, r, fps) if r and r[1] - r[0] > 0.3 else None
        if t and t > 0.5 and not any(c["debut"] <= 0.01 for c in cuts):
            cuts.append({"debut": 0.0, "fin": t, "mots": ["(attente avant de parler)"], "silence_debut": (0, 0), "silence_fin": r})
        r = find_run(runs, dernier["fin"] - 0.15, dernier["fin"] + 3.0)
        t = snap_in_run(r[0] + 0.4, r, fps) if r and r[1] - r[0] > 0.5 else None
        fin_video = math.floor(duration * fps) / fps
        if t and fin_video - t > 0.5 and not any(c["fin"] >= fin_video - 0.01 for c in cuts):
            cuts.append({"debut": t, "fin": fin_video, "mots": ["(fin après le dernier mot)"], "silence_debut": r, "silence_fin": (duration, duration)})
    # temps morts : toute pause de plus de pause_max entre deux mots gardés est raccourcie (coupe dans le silence)
    if pause_max:
        gardes_idx = [i for i, st in enumerate(status) if st not in ("reprise", "hesitation")]
        for a_i, b_i in zip(gardes_idx, gardes_idx[1:]):
            wa, wb = words[a_i], words[b_i]
            dedans = sum(max(0.0, min(c["fin"], wb["debut"]) - max(c["debut"], wa["fin"])) for c in cuts)
            if wb["debut"] - wa["fin"] - dedans <= pause_max:
                continue  # pause déjà assez courte (les coupes de reprise comprises)
            calmes = sorted(set(map(tuple, runs)) | set(map(tuple, breaths)))
            # premier moment calme après le dernier mot, dernier moment calme avant le mot suivant
            ra = next((r for r in calmes if r[1] > wa["fin"] - 0.15 and r[0] < wa["fin"] + 1.0 and r[0] > wa["debut"]), None)
            rb = next((r for r in reversed(calmes) if r[0] < wb["debut"] + 0.15 and r[1] > wb["debut"] - 1.2
                       and r[1] < wb["fin"]), None)
            if not ra or not rb or rb[1] <= ra[0]:
                continue
            garde = pause_max / 2
            t0 = snap_in_run(min(ra[0] + garde, (ra[0] + ra[1]) / 2), ra, fps)
            t1 = snap_in_run(max(rb[1] - garde, (rb[0] + rb[1]) / 2), rb, fps)
            if t0 is not None and t1 is not None and t1 - t0 >= 0.15:
                est_silence = lambda r: any(x[0] <= r[0] + 1e-6 and x[1] >= r[1] - 1e-6 for x in runs)
                cuts.append({"debut": t0, "fin": t1, "mots": ["(temps mort)"], "silence_debut": ra, "silence_fin": rb,
                             "seuil_debut": "silence" if est_silence(ra) else "respiration",
                             "seuil_fin": "silence" if est_silence(rb) else "respiration"})
    # fusionner les coupes qui se touchent
    cuts.sort(key=lambda c: c["debut"])
    fusion = []
    for c in cuts:
        if fusion and c["debut"] <= fusion[-1]["fin"]:
            fusion[-1]["fin"] = max(fusion[-1]["fin"], c["fin"])
            fusion[-1]["mots"] = fusion[-1]["mots"] + c["mots"]
        else:
            fusion.append(c)
    return fusion, refused


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


def render(video, segs, out, fps):
    """Chaque morceau gardé est encodé à part (calé sur ses images), puis les morceaux sont mis bout à bout.
    Le son reste en PCM jusqu'à l'assemblage pour éviter tout blanc ou clic aux raccords."""
    tmp = tempfile.mkdtemp(prefix="derush_morceaux_")
    liste = os.path.join(tmp, "liste.txt")
    with open(liste, "w") as f:
        for i, (a, b) in enumerate(segs):
            d = b - a
            n = round(d * fps)
            fade = min(0.005, d / 4)
            m = os.path.join(tmp, f"m{i:04d}.mkv")
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.6f}", "-i", video, "-frames:v", str(n), "-t", f"{d:.6f}",
                 "-af", f"afade=t=in:d={fade:.4f},afade=t=out:st={max(0, d - fade):.4f}:d={fade:.4f}",
                 "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", str(fps),
                 "-c:a", "pcm_s16le", "-ar", "48000", m])
            f.write(f"file '{m}'\n")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    shutil.rmtree(tmp, ignore_errors=True)


def to_output_time(t, cuts):
    return t - sum(max(0.0, min(c["fin"], t) - c["debut"]) for c in cuts if c["debut"] < t)


# ----------------------------------------------------------------------------- 5. vérifications
def verify(video_in, video_out, words, status, cuts, db, thr, engine_args, tmp, pause_thr=None):
    pause_thr = thr if pause_thr is None else pause_thr
    rep = {"raccords": [], "mots_manquants": [], "mots_coupes_par_erreur": []}
    # a) son à chaque raccord : juste avant et juste après chaque coupe, dans l'original et la sortie
    out_audio = extract_audio(video_out, os.path.join(tmp, "sortie.wav"))
    db_out = energy_db(out_audio)
    for c in cuts:
        before = level_max(db, c["debut"] - 0.03, c["debut"])
        after = level_max(db, c["fin"], c["fin"] + 0.03)
        t_out = to_output_time(c["debut"], cuts)
        at_join = level_max(db_out, t_out - 0.03, t_out + 0.03)
        t_av = pause_thr if c.get("seuil_debut") == "respiration" else thr
        t_ap = pause_thr if c.get("seuil_fin") == "respiration" else thr
        ok = before < t_av and after < t_ap and at_join < max(t_av, t_ap)
        rep["raccords"].append({"coupe": f"{c['debut']:.3f}s -> {c['fin']:.3f}s", "mots_retires": " ".join(c["mots"]),
                                "son_avant_db": round(before, 1), "son_apres_db": round(after, 1),
                                "son_au_raccord_sortie_db": round(at_join, 1), "seuil_db": round(max(t_av, t_ap), 1),
                                "dans": "respiration" if max(t_av, t_ap) > thr else "silence",
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
    ap.add_argument("--pause-max", type=float, default=0.5,
                    help="raccourcir les pauses plus longues que ça (secondes) ; 0 pour ne pas y toucher")
    ap.add_argument("--transcription", help="réutiliser la transcription d'un passage précédent (fichier _mots.json)")
    ap.add_argument("--couper-ajouts", action="store_true",
                    help="couper aussi les mots ajoutés hors script qui ne sont pas des reprises")
    args = ap.parse_args()

    out = args.sortie or os.path.splitext(args.video)[0] + "_derush.mp4"
    script_text = open(args.script, encoding="utf-8").read()
    fps, duration = probe(args.video)
    tmp = tempfile.mkdtemp(prefix="derush_")
    engine_args = (args.modele, "whisper" if args.moteur == "whisper" else None)

    print(f"▶ Vidéo : {args.video} ({duration:.2f} s, {fps:g} images/s)")
    audio = extract_audio(args.video, os.path.join(tmp, "original.wav"))
    if args.transcription:
        engine, reason, words = "transcription réutilisée", args.transcription, json.load(open(args.transcription))
    else:
        engine, reason, words = transcribe(os.path.join(tmp, "original.wav"), *engine_args)
        with open(os.path.splitext(out)[0] + "_mots.json", "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False)
    print(f"▶ Transcription : {engine} ({reason})")
    print("  Entendu : " + " ".join(w["mot"] for w in words))

    status = classify(script_text, words, args.couper_ajouts)
    db = energy_db(audio)
    calib = calibrate(db, words)
    thr = calib["seuil_silence_db"]
    runs = silent_runs(db, thr)
    print(f"▶ Calibrage du silence : bruit de fond {calib['bruit_de_fond_db']} dB, voix {calib['voix_db']} dB "
          f"-> seuil {thr} dB (respiration : {calib['seuil_respiration_db']} dB)")

    breaths = breath_runs(db, calib["seuil_respiration_db"], words)
    cuts, refused = plan_cuts(words, status, runs, fps, duration, breaths, args.pause_max)
    report = {"video": args.video, "sortie": out, "moteur_transcription": engine, "raison_moteur": reason,
              "images_par_seconde": fps, "calibrage": calib,
              "mots": [{**w, "decision": s} for w, s in zip(words, status)], "coupes_refusees": refused}

    for attempt in range(1, 4):
        segs = keep_segments(cuts, duration, fps)
        render(args.video, segs, out, fps)
        ver = verify(args.video, out, words, status, cuts, db, thr, engine_args, tmp, calib["seuil_respiration_db"])
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
              f"dans la sortie {r['son_au_raccord_sortie_db']} dB (seuil {r['seuil_db']}, coupe dans {r['dans']}) -> "
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
