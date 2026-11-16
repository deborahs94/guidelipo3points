#!/usr/bin/env python3
"""Fabrique un rush de test « face caméra » de 10 s (1080x1920, 30 i/s) :
un personnage dessiné dans un décor de cabine, qui respire et cligne des yeux,
avec une voix de synthèse française. Sert uniquement à tester le moteur."""
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "rush_test.mp4"
W, H, FPS, DUR = 1080, 1920, 30, 10.0
TEXTE = ("Tu fais du sport, tu manges bien, et pourtant ta cellulite ne bouge pas ? "
         "Ce n'est pas ta faute. En six séances, tu peux perdre cinq centimètres.")


def decor():
    img = Image.new("RGB", (W, H), "#EFE6DC")
    d = ImageDraw.Draw(img)
    for y in range(H):                       # mur crème en dégradé
        c = int(239 - 22 * y / H)
        d.line([(0, y), (W, y)], fill=(c, c - 9, c - 20))
    d.rectangle([0, 1450, W, H], fill="#D9C7B5")                     # meuble
    d.rectangle([720, 380, 1000, 760], outline="#6B1526", width=10)  # cadre bordeaux
    d.rectangle([745, 405, 975, 735], fill="#E4DCD1")
    d.ellipse([90, 1220, 330, 1460], fill="#BBA18E")                 # pot
    for a in range(-60, 61, 20):                                     # plante
        x = 210 + 260 * math.sin(math.radians(a))
        d.line([(210, 1260), (x, 930 + abs(a) * 2)], fill="#7E8C6A", width=14)
    return img.filter(ImageFilter.GaussianBlur(10))                  # arrière-plan flou


def personnage(img, t):
    d = ImageDraw.Draw(img)
    sway = 8 * math.sin(2 * math.pi * t / 3.2)
    bob = 5 * math.sin(2 * math.pi * t / 1.6)
    cx, cy = W / 2 + sway, 880 + bob
    d.ellipse([cx - 330, cy + 480, cx + 330, cy + 1300], fill="#1E1A1A")       # buste
    d.rectangle([cx - 70, cy + 230, cx + 70, cy + 520], fill="#D9B497")         # cou
    d.ellipse([cx - 260, cy - 330, cx + 260, cy + 260], fill="#3A2722")         # cheveux arrière
    d.ellipse([cx - 190, cy - 250, cx + 190, cy + 280], fill="#E2C0A4")         # visage
    d.chord([cx - 215, cy - 340, cx + 215, cy + 40], 180, 360, fill="#3A2722")  # frange
    blink = (t % 3.7) < 0.12
    for ex in (-80, 80):
        if blink:
            d.line([(cx + ex - 30, cy), (cx + ex + 30, cy)], fill="#2B1E1A", width=6)
        else:
            d.ellipse([cx + ex - 26, cy - 16, cx + ex + 26, cy + 16], fill="#FFFFFF")
            d.ellipse([cx + ex - 13, cy - 13, cx + ex + 13, cy + 13], fill="#3B2A20")
    talk = abs(math.sin(2 * math.pi * t * 4.3)) if t < 8.6 else 0
    d.ellipse([cx - 55, cy + 130 - 6, cx + 55, cy + 130 + 8 + 30 * talk], fill="#8E3B45")
    return img


base = decor()
ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                       "-crf", "20", OUT + ".video.mp4"], stdin=subprocess.PIPE)
for k in range(int(DUR * FPS)):
    ff.stdin.write(personnage(base.copy(), k / FPS).tobytes())
ff.stdin.close()
ff.wait()

subprocess.run(["espeak-ng", "-v", "fr-fr", "-s", "155", "-w", OUT + ".voix.wav", TEXTE], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", OUT + ".video.mp4", "-i", OUT + ".voix.wav",
                "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.003:r=48000",
                "-filter_complex", "[1:a]adelay=300|300,aresample=48000,apad[v];[v][2:a]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-t", str(DUR), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", OUT],
               check=True)
os.remove(OUT + ".video.mp4")
os.remove(OUT + ".voix.wav")
print("Rush de test :", OUT)
