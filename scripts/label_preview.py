"""Adds a caption band under a preview image listing what is estimated or assumed, so a preview is
never mistaken for verified fact.

    python3 scripts/label_preview.py in.png out.jpg "Title" "line 1" "line 2" ...
"""
import sys
from PIL import Image, ImageDraw, ImageFont

src, dst, title, *lines = sys.argv[1:]
img = Image.open(src).convert('RGB')
W, H = img.size
fs = max(13, W // 95)
font = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Light.otf', fs)
bold = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Regular.otf', int(fs * 1.1)) if __import__('os').path.exists('/usr/share/fonts/opentype/inter/Inter-Regular.otf') else font
pad, lh = fs, int(fs * 1.45)
band = pad * 2 + lh * (len(lines) + 1)
out = Image.new('RGB', (W, H + band), (24, 28, 34))
out.paste(img, (0, 0))
d = ImageDraw.Draw(out)
y = H + pad
d.text((pad, y), title, font=bold, fill=(255, 255, 255)); y += lh
for ln in lines:
    d.text((pad, y), ln, font=font, fill=(255, 214, 120) if ln.startswith(('ASSUMED', 'ESTIMATE')) else (205, 210, 216)); y += lh
out.save(dst, quality=92)
print('labelled', dst)
