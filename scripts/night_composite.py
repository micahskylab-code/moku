"""Builds the night film: each frame is cut from the path-traced 360 plate (exact for a camera that
only rotates and zooms), the real star field goes behind it, lights get a soft photographic bloom,
and the title fades in. Then ffmpeg encodes the MP4.

    python3 scripts/night_composite.py blender/timeline.json blender/plate.png blender/plate.json blender/stars out.mp4
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import map_coordinates

tl_path, plate_path, plate_meta, stars_dir, out_mp4 = sys.argv[1:6]
W, H = (int(v) for v in (sys.argv[6] if len(sys.argv) > 6 else '1920x1080').split('x'))
tl = json.load(open(tl_path)); pm = json.load(open(plate_meta))
plate = np.asarray(Image.open(plate_path).convert('RGBA')).astype(np.float32) / 255.0
PH, PW = plate.shape[:2]
frames_dir = os.path.join(os.path.dirname(out_mp4), 'night-frames'); os.makedirs(frames_dir, exist_ok=True)

font_big = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Light.otf', int(H * 0.05))
font_small = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Light.otf', int(H * 0.019))

# pixel grid in normalised device coordinates
jj, ii = np.mgrid[0:H, 0:W].astype(np.float32)
nx = (2 * (ii + 0.5) / W - 1)
ny = (1 - 2 * (jj + 0.5) / H)

def spaced(draw, text, font, y, tracking, alpha):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=(244, 239, 230, int(255 * alpha)))
        x += w + tracking

for i, f in enumerate(tl['frames']):
    vf = math.radians(f['fov']); t = math.tan(vf / 2)
    yaw, pitch = f['yaw'], f['pitch']
    fwd = np.array([math.cos(pitch) * math.cos(yaw), math.sin(pitch), math.cos(pitch) * math.sin(yaw)])
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    d = fwd[None, None, :] + (nx * t * W / H)[..., None] * right + (ny * t)[..., None] * up
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    lon = np.arctan2(d[..., 0], -d[..., 2])                 # three.js direction -> equirect longitude
    lat = np.arcsin(np.clip(d[..., 1], -1, 1))
    px = (0.5 + lon / (2 * math.pi)) * pm['W'] - pm['x0'] - 0.5
    py = (0.5 - lat / math.pi) * pm['H'] - pm['y0'] - 0.5
    rgba = np.stack([map_coordinates(plate[..., c], [py, px], order=1, mode='nearest') for c in range(4)], axis=-1)
    stars = np.asarray(Image.open(os.path.join(stars_dir, f's{i:05d}.png')).convert('RGB').resize((W, H))).astype(np.float32) / 255.0
    a = rgba[..., 3:4]
    img = rgba[..., :3] * a + stars * (1 - a)
    # bloom on the warm lights and the pool glow
    lum = img.max(axis=2)
    hot = np.clip((lum - 0.72) / 0.28, 0, 1)[..., None] * img
    hot_img = Image.fromarray((hot * 255).astype(np.uint8))
    bloom = (np.asarray(hot_img.filter(ImageFilter.GaussianBlur(H * 0.012))).astype(np.float32) / 255.0 * 0.55
             + np.asarray(hot_img.filter(ImageFilter.GaussianBlur(H * 0.035))).astype(np.float32) / 255.0 * 0.35)
    img = 1 - (1 - img) * (1 - bloom)
    # gentle vignette
    vig = 1 - 0.22 * (nx ** 2 + ny ** 2) ** 1.2
    img = np.clip(img * vig[..., None], 0, 1)
    out = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    if f['caption'] > 0.01:
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(layer)
        spaced(dr, 'NĀ HIKU', font_big, H * 0.80, H * 0.022, f['caption'])
        spaced(dr, 'THE SEVEN STARS OVER KUKUIʻULA', font_small, H * 0.80 + H * 0.075, H * 0.008, f['caption'] * 0.85)
        shadow = layer.filter(ImageFilter.GaussianBlur(H * 0.01)); sh = np.asarray(shadow).astype(np.float32); sh[..., :3] = 0; sh[..., 3] *= 0.6
        out = Image.alpha_composite(out.convert('RGBA'), Image.fromarray(sh.astype(np.uint8)))
        out = Image.alpha_composite(out, layer).convert('RGB')
    out.save(os.path.join(frames_dir, f'f{i:05d}.png'))
    if i % 48 == 0: print('frame', i, flush=True)

ff = os.environ.get('FFMPEG') or subprocess.check_output(['python3', '-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())']).decode().strip()
subprocess.check_call([ff, '-y', '-framerate', str(tl['fps']), '-i', os.path.join(frames_dir, 'f%05d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-movflags', '+faststart', out_mp4])
print('wrote', out_mp4)
