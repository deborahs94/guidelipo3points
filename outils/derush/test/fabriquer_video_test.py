#!/usr/bin/env python3
"""Fabrique une courte vidéo face caméra de test, avec une voix de synthèse française.

Elle contient volontairement :
  - une phrase commencée puis reprise (« ... la lipo » puis la phrase complète),
  - une hésitation (« euh »),
  - un mot prononcé tout doucement (« doux », 14 dB plus bas) qui ne doit PAS être coupé,
  - une phrase répétée deux fois (il faut garder la dernière),
  - un léger bruit de fond (pour que le calibrage du silence ait du sens),
  - un compteur d'images à l'écran (pour contrôler la synchro).
"""
import os
import subprocess
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "video_test.mp4"
TMP = os.path.splitext(OUT)[0] + "_morceaux"
os.makedirs(TMP, exist_ok=True)

# (texte prononcé, gain en dB, silence après en secondes)
TAKES = [
    ("Bonjour, je m'appelle Déborah.", 0, 0.7),
    ("Aujourd'hui, je t'explique la lipo", 0, 0.6),          # reprise ratée
    ("euh", 0, 0.6),                                           # hésitation
    ("Aujourd'hui, je t'explique la lipocavitation.", 0, 0.7),
    ("C'est un soin", 0, 0.3),
    ("doux", -14, 0.3),                                        # mot dit tout doucement
    ("et efficace.", 0, 0.7),
    ("Prends rendez-vous sur mon", 0, 0.6),                    # phrase répétée
    ("Prends rendez-vous sur mon site.", 0, 0.8),
]
SCRIPT = ("Bonjour, je m'appelle Déborah. Aujourd'hui, je t'explique la lipocavitation. "
          "C'est un soin doux et efficace. Prends rendez-vous sur mon site.")


def sh(cmd):
    subprocess.run(cmd, check=True)


parts = []
for i, (text, gain, pause) in enumerate(TAKES):
    raw = f"{TMP}/{i:02d}_voix.wav"
    sh(["espeak-ng", "-v", "fr-fr", "-s", "150", "-w", raw, text])
    seg = f"{TMP}/{i:02d}.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
        f"volume={gain}dB,aresample=48000,apad=pad_dur={pause}", "-ac", "1", seg])
    parts.append(seg)

lead = f"{TMP}/debut.wav"
sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.6", lead])
with open(f"{TMP}/liste.txt", "w") as f:
    for p in [lead] + parts:
        f.write(f"file '{os.path.abspath(p)}'\n")
voice = f"{TMP}/voix.wav"
sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{TMP}/liste.txt", "-c", "copy", voice])

dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", voice],
                     capture_output=True, text=True, check=True).stdout.strip()
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
sh(["ffmpeg", "-y", "-v", "error", "-i", voice,
    "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.004:r=48000",
    "-f", "lavfi", "-i", "color=c=0xF8F6F1:s=540x960:r=30",
    "-filter_complex",
    "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a];"
    f"[2:v]drawtext=fontfile={font}:text='IMAGE %{{frame_num}}':fontcolor=0x6B1526:fontsize=56:"
    "x=(w-tw)/2:y=h/2-60,"
    f"drawtext=fontfile={font}:text='%{{pts\\:hms}}':fontcolor=0x181818:fontsize=40:x=(w-tw)/2:y=h/2+20[v]",
    "-map", "[v]", "-map", "[a]", "-t", dur, "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", OUT])

with open(os.path.splitext(OUT)[0] + "_script.txt", "w", encoding="utf-8") as f:
    f.write(SCRIPT + "\n")
print("Vidéo de test :", OUT)
