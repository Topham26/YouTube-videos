#!/usr/bin/env python3
"""Generate a 1280x720 YouTube thumbnail reusing the video's background look."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import build_video as bv

OUT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(OUT)
TW, TH = 1280, 720
FONT_DIR = bv.FONT_DIR


def main():
    bg = bv.make_background()
    # center crop to 16:9 and resize to 1280x720
    img = Image.fromarray(bg)
    # crop a strong region near the throne glow
    cx = int(bv.BW * 0.5); cy = int(bv.BH * 0.42)
    cw, ch = int(bv.BH * 16 / 9), bv.BH
    left = max(0, cx - cw // 2)
    img = img.crop((left, 0, left + cw, ch)).resize((TW, TH), Image.LANCZOS)

    d = ImageDraw.Draw(img, "RGBA")
    # darken lower third for text
    scrim = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(TH):
        a = int(150 * max(0, (i - TH * 0.45) / (TH * 0.55)))
        sd.line([(0, i), (TW, i)], fill=(3, 4, 12, a))
    img = Image.alpha_composite(img.convert("RGBA"), scrim)
    d = ImageDraw.Draw(img)

    f_big = ImageFont.truetype(os.path.join(FONT_DIR, "IBMPlexSerif-Bold.ttf"), 132)
    f_sub = ImageFont.truetype(os.path.join(FONT_DIR, "IBMPlexSerif-Italic.ttf"), 46)
    f_tag = ImageFont.truetype(os.path.join(FONT_DIR, "IBMPlexSerif-Regular.ttf"), 38)

    def centered(text, font, y, fill, glow=None):
        tw = d.textlength(text, font=font)
        x = (TW - tw) / 2
        if glow:
            g = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            gd.text((x, y), text, font=font, fill=glow)
            g = g.filter(ImageFilter.GaussianBlur(12))
            img.alpha_composite(g)
        # shadow
        d.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 210))
        d.text((x, y), text, font=font, fill=fill)

    centered("HOLY, HOLY,", f_big, 150, (236, 205, 132, 255), glow=(232, 200, 128, 255))
    centered("HOLY", f_big, 285, (236, 205, 132, 255), glow=(232, 200, 128, 255))
    centered("The Council of the Holy Ones", f_sub, 452, (245, 240, 228, 255))
    centered("Psalm 82 · Deuteronomy 32 · Isaiah 6", f_tag, 620, (188, 178, 158, 255))

    out = os.path.join(PROJ, "thumbnail.png")
    img.convert("RGB").save(out, quality=95)
    print("wrote", out)


if __name__ == "__main__":
    main()
