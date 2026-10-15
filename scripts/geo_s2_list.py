#!/usr/bin/env python3
"""List Sentinel-2 L2A scenes over south Kaua'i (MGRS 04QDK) with their tile-level cloud cover.

Writes <cache>/s2_scenes.json: [{id, date, cloud, nodata, prefix}], sorted by cloud cover.
Source: Sentinel-2 L2A COGs on AWS (s3://sentinel-cogs, Element 84 / ESA Copernicus, open data:
Copernicus Sentinel data, free and open licence).
    python3 scripts/geo_s2_list.py <cache_dir> [years...]
"""
import json, re, sys, urllib.request, concurrent.futures as cf

BUCKET = 'https://sentinel-cogs.s3.us-west-2.amazonaws.com'
TILE = 'sentinel-s2-l2a-cogs/4/Q/DK'


def ls(prefix, delim=True):
    keys, prefixes, token = [], [], None
    while True:
        q = f'{BUCKET}/?list-type=2&prefix={prefix}' + ('&delimiter=/' if delim else '') + (f'&continuation-token={urllib.parse.quote(token)}' if token else '')
        x = urllib.request.urlopen(q, timeout=60).read().decode()
        keys += re.findall(r'<Key>([^<]*)</Key>', x)
        prefixes += re.findall(r'<Prefix>([^<]*)</Prefix>', x)[1:]
        m = re.search(r'<NextContinuationToken>([^<]*)</NextContinuationToken>', x)
        if not m: return keys, prefixes
        token = m.group(1)


def item(prefix):
    sid = prefix.rstrip('/').split('/')[-1]
    try:
        d = json.load(urllib.request.urlopen(f'{BUCKET}/{prefix}{sid}.json', timeout=60))
        p = d['properties']
        return {'id': sid, 'prefix': prefix, 'date': p['datetime'], 'cloud': p.get('eo:cloud_cover'), 'nodata': p.get('s2:nodata_pixel_percentage'),
                'sun_el': p.get('view:sun_elevation'), 'sun_az': p.get('view:sun_azimuth')}
    except Exception as e:
        return {'id': sid, 'prefix': prefix, 'error': str(e)}


if __name__ == '__main__':
    import urllib.parse
    cache = sys.argv[1]
    years = sys.argv[2:] or ['2023', '2024', '2025', '2026']
    scenes = []
    for y in years:
        _, months = ls(f'{TILE}/{y}/')
        for m in months:
            _, sc = ls(m)
            scenes += sc
    with cf.ThreadPoolExecutor(12) as ex:
        items = list(ex.map(item, scenes))
    items = [i for i in items if 'cloud' in i and i['cloud'] is not None]
    items.sort(key=lambda i: i['cloud'])
    json.dump(items, open(f'{cache}/s2_scenes.json', 'w'), indent=1)
    for i in items[:40]: print(i['id'], i['date'][:10], round(i['cloud'], 1), round(i['nodata'] or 0, 1))
    print(len(items), 'scenes')
