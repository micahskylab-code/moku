#!/usr/bin/env python3
"""Pull Overture Maps features (OSM / Microsoft / Esri community data, ODbL & CDLA) for a lon/lat box
straight from the public GeoParquet release on S3, reading only the row groups whose bbox overlaps.
    python3 scripts/geo_overture.py <cache_dir> <theme/type> [lon0 lat0 lon1 lat1] [release]
e.g. transportation/segment, buildings/building, base/land_use, base/water, base/land_cover
Writes <cache>/ov_<type>.json: list of {id, geometry (WKB hex), plus selected properties}.
"""
import io, json, os, re, sys, urllib.request, concurrent.futures as cf
import pyarrow.parquet as pq

BUCKET = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com'


class RangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests (honours HTTPS_PROXY)."""
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0: return 0
        for attempt in range(5):
            try:
                req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos + n - 1}'})
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except Exception:
                if attempt == 4: raise
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def listing(prefix):
    out, token = [], None
    while True:
        q = f'{BUCKET}/?list-type=2&prefix={prefix}' + (f'&continuation-token={urllib.parse.quote(token)}' if token else '')
        x = urllib.request.urlopen(q, timeout=60).read().decode()
        out += [(k, int(s)) for k, s in re.findall(r'<Key>([^<]*)</Key>.*?<Size>(\d+)</Size>', x)]
        m = re.search(r'<NextContinuationToken>([^<]*)</NextContinuationToken>', x)
        if not m: return out
        token = m.group(1)


def scan(key, size, box):
    f = pq.ParquetFile(io.BufferedReader(RangeFile(f'{BUCKET}/{key}', size), buffer_size=1 << 20))
    md = f.metadata
    names = [md.schema.column(i).path for i in range(md.num_columns)]
    ix = {k: names.index(f'bbox.{k}') for k in ('xmin', 'xmax', 'ymin', 'ymax')}
    groups = []
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = {k: rg.column(i).statistics for k, i in ix.items()}
        if any(s is None or not s.has_min_max for s in st.values()): continue
        if st['xmin'].min > box[2] or st['xmax'].max < box[0] or st['ymin'].min > box[3] or st['ymax'].max < box[1]: continue
        groups.append(g)
    rows = []
    for g in groups:
        t = f.read_row_group(g).to_pylist()
        for r in t:
            b = r['bbox']
            if b['xmin'] > box[2] or b['xmax'] < box[0] or b['ymin'] > box[3] or b['ymax'] < box[1]: continue
            r['geometry'] = r['geometry'].hex() if isinstance(r['geometry'], (bytes, bytearray)) else r['geometry']
            rows.append(r)
    return key, len(groups), rows


def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k, x in v.items() if x is not None}
    if isinstance(v, list): return [clean(x) for x in v]
    return v


if __name__ == '__main__':
    import urllib.parse
    cache, tt = sys.argv[1], sys.argv[2]
    box = [float(v) for v in sys.argv[3:7]] if len(sys.argv) >= 7 else [-159.56, 21.86, -159.40, 21.96]
    rel = sys.argv[7] if len(sys.argv) >= 8 else '2026-09-23.0'
    theme, typ = tt.split('/')
    files = [(k, s) for k, s in listing(f'release/{rel}/theme={theme}/type={typ}/') if k.endswith('.parquet')]
    rows = []
    with cf.ThreadPoolExecutor(8) as ex:
        for key, ng, r in ex.map(lambda ks: scan(ks[0], ks[1], box), files):
            if r: print(key.split('/')[-1][:12], ng, 'groups', len(r), 'rows', flush=True)
            rows += r
    json.dump([clean(r) for r in rows], open(f'{cache}/ov_{typ}.json', 'w'), default=str)
    print(typ, len(rows), 'features')
