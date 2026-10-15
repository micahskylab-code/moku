"""Photographic finish for the Cycles renders: what a real camera and an arch-viz grade add on top of
a clean path-traced frame. Every step is subtle on purpose — overdone post-processing reads as fake.

    python3 scripts/photo_finish.py in.png out.png [--ref ref/front.png] [--mist in.mist.png] [--strength 1]

 1. colour grade toward a reference photo (Lab mean/spread transfer, partial)
 2. aerial perspective: distant things fade toward the horizon colour (needs the mist pass)
 3. highlight glow (lens bloom) on sun-lit white, water glints and lamps
 4. lateral chromatic aberration toward the frame edges
 5. lens vignette
 6. fine luminance grain and a light unsharp mask (camera sharpening)
"""
import argparse
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--ref', default='')
ap.add_argument('--mist', default='')
ap.add_argument('--strength', type=float, default=1.0)
ap.add_argument('--grade', type=float, default=0.4, help='how far to move toward the reference grade (0..1)')
ap.add_argument('--haze', type=float, default=0.22)
ap.add_argument('--seed', type=int, default=7)
a = ap.parse_args()
K = a.strength


def srgb_to_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)

M_XYZ = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
WHITE = np.array([0.95047, 1.0, 1.08883])


def to_lab(rgb):
    xyz = srgb_to_lin(rgb) @ M_XYZ.T / WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def from_lab(lab):
    fy = (lab[..., 0] + 16) / 116; fx = fy + lab[..., 1] / 500; fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * WHITE
    return np.clip(lin_to_srgb(xyz @ np.linalg.inv(M_XYZ).T), 0, 1)


img = np.asarray(Image.open(a.src).convert('RGB')).astype(np.float64) / 255.0
H, W = img.shape[:2]

# 1. grade toward the reference: match the mean and spread of each Lab channel, partially
if a.ref and a.grade > 0:
    ref = Image.open(a.ref).convert('RGB'); ref.thumbnail((800, 800))
    rl = to_lab(np.asarray(ref).astype(np.float64) / 255.0).reshape(-1, 3)
    il = to_lab(img)
    flat = il.reshape(-1, 3)
    mu_i, sd_i = flat.mean(0), flat.std(0) + 1e-6
    mu_r, sd_r = rl.mean(0), rl.std(0) + 1e-6
    t = a.grade * K
    scale = 1 + t * (sd_r / sd_i - 1); shift = t * (mu_r - mu_i)
    scale[0] = np.clip(scale[0], 0.85, 1.15); shift[0] = np.clip(shift[0], -6, 6)     # keep the exposure honest
    il = (il - mu_i) * scale + mu_i + shift
    img = from_lab(il)

lin = srgb_to_lin(img)

# 2. aerial perspective from the mist pass (0 near .. 1 far)
if a.mist:
    mist = np.asarray(Image.open(a.mist).convert('L').resize((W, H))).astype(np.float64) / 255.0
    sky_rows = lin[: max(4, H // 12)].reshape(-1, 3)
    horizon = np.median(sky_rows, axis=0) * 0.85 + np.array([0.55, 0.62, 0.72]) * 0.15
    k = (np.clip(mist, 0, 1) ** 1.6 * a.haze * K)[..., None]
    lin = lin * (1 - k) + horizon * k

# 3. highlight glow: only what is genuinely bright spills a little light around it
lum = lin @ np.array([0.2126, 0.7152, 0.0722])
hot = np.clip((lum - 0.75) / 0.6, 0, 1)[..., None] * lin
glow = sum(w * gaussian_filter(hot, sigma=(s * H / 1000, s * H / 1000, 0)) for s, w in ((3, 0.5), (12, 0.35), (40, 0.15)))
lin = lin + glow * 0.18 * K

# 4. lateral chromatic aberration: red slightly outward, blue slightly inward, growing to the edges
yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
cx, cy = (W - 1) / 2, (H - 1) / 2
dx, dy = (xx - cx) / cx, (yy - cy) / cy
r2 = dx * dx + dy * dy
ca = 0.7 * K * (min(W, H) / 1200)
out = np.empty_like(lin)
for ch, s in ((0, ca), (1, 0.0), (2, -ca)):
    if s == 0: out[..., ch] = lin[..., ch]; continue
    sx = xx + dx * r2 * s; sy = yy + dy * r2 * s
    out[..., ch] = map_coordinates(lin[..., ch], [sy, sx], order=1, mode='nearest')
lin = out

# 5. vignette (cos^4-like falloff, gentle)
vig = 1 - 0.16 * K * np.clip(r2 / 2, 0, 1) ** 1.3
lin = lin * vig[..., None]

img = lin_to_srgb(np.clip(lin, 0, None))
img = np.clip(img, 0, 1)

# 6. camera sharpening + fine grain (luminance, stronger in the shadows like a real sensor)
blur = gaussian_filter(img, sigma=(0.9, 0.9, 0))
img = np.clip(img + (img - blur) * 0.35 * K, 0, 1)
rng = np.random.default_rng(a.seed)
grain = gaussian_filter(rng.normal(0, 1, (H, W)), 0.55)
grain /= grain.std() + 1e-9
l = img.mean(2, keepdims=True)
img = np.clip(img + grain[..., None] * (0.010 + 0.012 * (1 - l)) * K, 0, 1)

Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(a.dst, quality=95)
print('finished', a.dst)
