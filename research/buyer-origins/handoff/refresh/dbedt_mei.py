"""DBEDT Monthly Economic Indicators: county home resales and medians.

Discovers the latest county workbooks from DBEDT's publisher page, extracts the
monthly single-family and condo resale counts and median prices for the four
counties, validates them, detects new releases and revisions to earlier
months, and keeps the last fully validated dataset when anything fails.

Standard library only (xlsx_lite reads the workbooks). Run it with run_refresh.py.

Rules this module enforces:
- Values are copied as published. "(NA)" and blanks stay missing (None), never 0.
- Medians are never computed, averaged or combined across counties or months.
  There is no statewide median (DBEDT publishes "(NA)" for it).
- Monthly values and year-to-date values are kept in separate structures.
- YTD counts are sums of published monthly counts, and only when every month
  from January through the "through" month is present.
- The last-good dataset is replaced only by a candidate that passes every
  check and has all four counties complete for its observation month.
- Nothing here edits report text, explanations or forecasts.
"""
import datetime
import hashlib
import html as htmllib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from xlsx_lite import Workbook, XlsxError, excel_serial_to_date

SCHEMA_VERSION = 1
DATASET_ID = 'dbedt_mei_county_housing'
PUBLISHER_PAGE = 'https://dbedt.hawaii.gov/economic/mei/'
ALLOWED_HOSTS = ('dbedt.hawaii.gov', 'files.hawaii.gov')
COUNTIES = ('honolulu', 'maui', 'kauai', 'hawaii')
COUNTY_META = {
    'honolulu': {'name': 'Honolulu County', 'island': 'Oʻahu', 'summary_geo': 'HONOLULU'},
    'maui': {'name': 'Maui County', 'island': 'Maui, Molokaʻi and Lānaʻi', 'summary_geo': 'MAUI'},
    'kauai': {'name': 'Kauaʻi County', 'island': 'Kauaʻi', 'summary_geo': 'KAUAI'},
    'hawaii': {'name': 'Hawaiʻi County', 'island': 'Hawaiʻi Island', 'summary_geo': 'HAWAII'},
}
FIELDS = ('sf_sales', 'sf_median', 'condo_sales', 'condo_median')
COUNT_FIELDS = ('sf_sales', 'condo_sales')
MEDIAN_OF = {'sf_median': 'sf_sales', 'condo_median': 'condo_sales'}
FIELD_META = {
    'sf_sales': {'label': 'Single-family home resales', 'unit': 'count', 'period': 'calendar month'},
    'sf_median': {'label': 'Single-family median selling price', 'unit': 'USD', 'period': 'calendar month'},
    'condo_sales': {'label': 'Condo/apartment/townhouse unit resales', 'unit': 'count', 'period': 'calendar month'},
    'condo_median': {'label': 'Condo/apartment/townhouse median price', 'unit': 'USD', 'period': 'calendar month'},
}
# County workbook: the six housing columns, located by header text (not position).
COUNTY_HEADERS = [
    ('sf_sales', 'single-family home resales', 'number'),
    ('sf_median', 'median selling price', '$'),
    (None, 'inventory (aver. units on market)', 'number'),
    ('condo_sales', 'condo/apt/townhouse units resales', 'number'),
    ('condo_median', 'median price', '$'),
    (None, 'inventory (aver. units on market)', 'number'),
]
SUMMARY_LABELS = [
    ('sf_sales', 'single-family home resales'),
    ('sf_median', 'median selling price'),
    ('condo_sales', 'condo/apt/townhouse units resales'),
    ('condo_median', 'median price'),
]
NA_TOKENS = {'', '(na)', 'na', 'n/a', '(d)', '-', '--', '—', '–', '(x)'}
SMALL_N = 20
MEDIAN_RANGE = (50_000, 25_000_000)   # outside this: warning, not failure
MAX_MONTHLY_COUNT = 2_000             # per county and type; above this: warning
MASS_REVISION_MIN = 12                # more changed earlier values than this ...
MASS_REVISION_SHARE = 0.01            # ... and above this share of overlapping values fails the run
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
          'september', 'october', 'november', 'december']
DATASET_FILE = 'dbedt_mei_county_housing.json'
LATEST_FILE = 'latest.json'

METHODOLOGY = {
    'source': ('DBEDT Monthly Economic Indicators (MEI) county workbooks. DBEDT compiles the housing rows from '
               'Honolulu Board of REALTORS, Hawaii Information Service, Title Guaranty of Hawaii and REALTORS '
               'Association of Maui data (workbook source note). Counts are MLS resales; they are not recorded-deed counts.'),
    'extraction': ('Housing columns are located by their header text and units row, not by position. The date column '
                   'is read as Excel serial dates and must form consecutive calendar months. Values are copied as published.'),
    'missing_values': 'Blank cells and "(NA)" stay null. A null is never replaced by 0, carried forward or interpolated.',
    'medians': ('Medians are the publisher\'s monthly medians. No median is computed, averaged or combined across '
                'counties, months or years. DBEDT publishes no statewide median, and none is derived here.'),
    'ytd': ('Year-to-date counts are sums of published monthly counts, computed only when every month from January '
            'through the "through" month is present for that county and type. YTD medians appear only as the values '
            'DBEDT itself publishes in its summary workbook.'),
    'state_counts': 'Statewide counts are the sum of the four county counts, only for months where all four are present.',
    'small_samples': ('A median based on fewer than 20 sales is listed under small_sample for that month. It is published '
                      'data, but month-to-month changes in it are mostly noise.'),
    'revisions': ('Each run compares every earlier month with the last-good dataset and with the verified report baseline. '
                  'Changed or removed values are listed with old and new values. Publisher revisions are applied to the '
                  'data, never to report text, explanations or forecasts.'),
    'not_live': ('Publisher-timed monthly data (released about 4-5 weeks after the month ends). A publication check is not '
                 'a real-time transaction feed.'),
}


# ----------------------------------------------------------------- utilities
def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _norm(s):
    s = re.sub(r'\s+', ' ', str(s or '')).strip().lower()
    s = re.sub(r'\s*(\d+/|\[[a-z]\]|\(level \d\)|\(note \d+\))\s*', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _month_key(y, m):
    return '%04d-%02d' % (y, m)


def _parse_month_name(name):
    n = name.strip().lower()
    return MONTHS.index(n) + 1 if n in MONTHS else None


def _parse_long_date(text):
    """'October 1, 2026' -> '2026-10-01'; None if not a full date."""
    m = re.match(r'\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', text or '')
    if not m or not _parse_month_name(m.group(1)):
        return None
    try:
        return datetime.date(int(m.group(3)), _parse_month_name(m.group(1)), int(m.group(2))).isoformat()
    except ValueError:
        return None


def _add_months(key, n):
    y, m = int(key[:4]), int(key[5:7])
    t = y * 12 + (m - 1) + n
    return _month_key(t // 12, t % 12 + 1)


def _host_allowed(url):
    h = (urllib.parse.urlparse(url).hostname or '').lower()
    return urllib.parse.urlparse(url).scheme == 'https' and h in ALLOWED_HOSTS


def write_json_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    os.replace(tmp, path)


def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def check(checks, cid, ok, detail, level='fail'):
    """Record one validation check. level='warn' marks a non-blocking problem."""
    checks.append({'id': cid, 'status': 'pass' if ok else level, 'detail': detail})
    return ok


# ----------------------------------------------------------------- fetching
class FetchResult:
    def __init__(self, url, status, data, headers, retrieved_utc, error=None, final_url=None):
        self.url, self.status, self.data, self.headers = url, status, data, headers or {}
        self.retrieved_utc, self.error, self.final_url = retrieved_utc, error, final_url or url

    @property
    def ok(self):
        return self.error is None and self.status == 200 and self.data is not None


class HttpFetcher:
    """HTTPS GET with a timeout and two bounded retries. Only DBEDT hosts are allowed."""

    def __init__(self, timeout=60, retries=2, user_agent=None, clock=utc_now):
        self.timeout, self.retries, self.user_agent, self.clock = timeout, retries, user_agent, clock

    def get(self, url):
        if not _host_allowed(url):
            return FetchResult(url, None, None, {}, self.clock(), error='host not allowed: %s' % url)
        headers = {'User-Agent': self.user_agent} if self.user_agent else {}
        last = None
        for attempt in range(self.retries + 1):
            stamp = self.clock()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=self.timeout) as r:
                    data = r.read()
                    final = r.geturl()
                    if not _host_allowed(final):
                        return FetchResult(url, r.status, None, {}, stamp, error='redirected off allowed hosts: %s' % final)
                    hdr = {k.lower(): v for k, v in r.headers.items()
                           if k.lower() in ('last-modified', 'etag', 'content-type', 'content-length')}
                    return FetchResult(url, r.status, data, hdr, stamp, final_url=final)
            except urllib.error.HTTPError as e:
                last = FetchResult(url, e.code, None, {}, stamp, error='HTTP %s' % e.code)
                if e.code in (404, 410, 403):
                    return last
            except Exception as e:  # network errors, timeouts
                last = FetchResult(url, None, None, {}, stamp, error='%s: %s' % (type(e).__name__, e))
            if attempt < self.retries:
                time.sleep(2 ** (attempt + 1))
        return last


class DirectoryFetcher:
    """Offline fetcher for tests and reproducible re-runs: serves files from a folder.

    The publisher page is read from `page_file`; every other URL is served by its
    file name. A missing file behaves like an HTTP 404.
    """

    def __init__(self, folder, page_file='mei_index.html', now='2026-10-09T00:00:00Z', overrides=None):
        self.folder, self.page_file, self.now = folder, page_file, now
        self.overrides = overrides or {}

    def get(self, url):
        if url in self.overrides:
            o = self.overrides[url]
            if isinstance(o, Exception):
                return FetchResult(url, None, None, {}, self.now, error='%s: %s' % (type(o).__name__, o))
            if isinstance(o, int):
                return FetchResult(url, o, None, {}, self.now, error='HTTP %s' % o)
            return FetchResult(url, 200, o, {}, self.now)
        name = self.page_file if url == PUBLISHER_PAGE else os.path.basename(urllib.parse.urlparse(url).path)
        path = os.path.join(self.folder, name)
        if not os.path.exists(path):
            return FetchResult(url, 404, None, {}, self.now, error='HTTP 404')
        with open(path, 'rb') as f:
            return FetchResult(url, 200, f.read(), {}, self.now)


# ----------------------------------------------------------------- discovery
_COUNTY_FILE = re.compile(r'/(\d{4})-(\d{2})-(honolulu|hawaii|maui|kauai)\.xlsx$', re.I)
_SUMMARY_FILE = re.compile(r'/mei-(\d{2})([a-z]?)-(\d{4})\.xlsx$', re.I)


def discover(page_html, page_url=PUBLISHER_PAGE):
    """Find the latest complete set of county workbooks linked from the publisher page."""
    out = {'periods': {}, 'summaries': {}, 'page_statements': [], 'problems': []}
    for href, inner in re.findall(r'<a\b[^>]*?\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, flags=re.S | re.I):
        url = urllib.parse.urljoin(page_url, htmllib.unescape(href.strip()))
        text = re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', inner))).strip()
        path = urllib.parse.urlparse(url).path
        m = _COUNTY_FILE.search(path)
        if m:
            if not _host_allowed(url):
                out['problems'].append('county workbook link on a non-DBEDT host ignored: %s' % url)
                continue
            period, county = _month_key(int(m.group(1)), int(m.group(2))), m.group(3).lower()
            slot = out['periods'].setdefault(period, {})
            if county in slot and slot[county]['url'] != url:
                out['problems'].append('two different %s workbooks for %s' % (county, period))
            slot[county] = {'url': url, 'link_text': text}
            continue
        m = _SUMMARY_FILE.search(path)
        if m and _host_allowed(url):
            period = _month_key(int(m.group(3)), int(m.group(1)))
            out['summaries'][period] = {'url': url, 'link_text': text, 'file_suffix': m.group(2) or ''}
    plain = re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', page_html)))
    for m in re.finditer(r'Monthly Economic Indicators \(MEI\) through [A-Z][a-z]+ \d{4} (?:was|will be)[^.]{0,200}\.', plain):
        if m.group(0) not in out['page_statements']:
            out['page_statements'].append(m.group(0))
    complete = sorted(p for p, s in out['periods'].items() if all(c in s for c in COUNTIES))
    out['latest_complete_period'] = complete[-1] if complete else None
    out['latest_listed_period'] = max(out['periods']) if out['periods'] else None
    return out


# ----------------------------------------------------------------- parsing
def _value(v, kind):
    """Return (value, problem). kind: 'count' or 'median'."""
    if v is None:
        return None, None
    if isinstance(v, bool):
        return None, 'boolean cell'
    if isinstance(v, str):
        if v.strip().lower() in NA_TOKENS:
            return None, None
        return None, 'non-numeric text %r' % v[:40]
    if kind == 'count':
        if v < 0 or v != int(v):
            return None, 'count is not a non-negative whole number: %r' % v
        return int(v), None
    if v <= 0:
        return None, 'median is not positive: %r' % v
    return (int(v) if v == int(v) else v), None


def parse_county_workbook(data, county):
    """Extract the county's monthly housing series. Raises XlsxError for unreadable files."""
    wb = Workbook(data)
    rows = wb.rows(0)
    res = {'county': county, 'sheet': wb.sheet_names[0], 'errors': [], 'warnings': [], 'months': {}}
    title = next((c for r in rows[:2] for c in r if isinstance(c, str) and c.strip()), '')
    res['title'] = title.strip()
    m = re.search(r'through\s+([A-Za-z]+)\s+(\d{4})', title)
    res['through'] = _month_key(int(m.group(2)), _parse_month_name(m.group(1))) if m and _parse_month_name(m.group(1)) else None
    m = re.search(r'was released on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})', title)
    res['released_on'] = _parse_long_date(m.group(1)) if m else None
    m = re.search(r'will be updated on\s+([^.;]*?\d{1,2}(?:,\s*\d{4})?)', title)
    res['update_statement'] = m.group(0).strip(' ,') if m else None

    hdr_i = next((i for i, r in enumerate(rows) if r and _norm(r[0]) == 'series'), None)
    if hdr_i is None or hdr_i + 1 >= len(rows) or not rows[hdr_i + 1] or _norm(rows[hdr_i + 1][0]) != 'unit':
        res['errors'].append('layout: header row "Series" followed by "UNIT" not found')
        return res
    hdr, unit = rows[hdr_i], rows[hdr_i + 1]
    starts = [j for j, h in enumerate(hdr) if _norm(h) == COUNTY_HEADERS[0][1]]
    if len(starts) != 1:
        res['errors'].append('layout: expected one "Single-family home resales" column, found %d' % len(starts))
        return res
    col = {}
    for k, (field, label, u) in enumerate(COUNTY_HEADERS):
        j = starts[0] + k
        h = _norm(hdr[j]) if j < len(hdr) else ''
        uu = _norm(unit[j]) if j < len(unit) else ''
        if h != label or uu != u:
            res['errors'].append('layout: column %d expected %r (%s), found %r (%s)' % (j, label, u, h, uu))
        elif field:
            col[field] = j
    if res['errors']:
        return res
    res['columns'] = col

    prev, started = None, False
    for r in rows[hdr_i + 2:]:
        a = r[0] if r else None
        if isinstance(a, (int, float)) and not isinstance(a, bool) and 30000 <= a <= 80000:
            d = excel_serial_to_date(a, wb.date1904)
            if d.day != 1:
                res['errors'].append('date column: %s is not the first of a month' % d.isoformat())
                break
            key = _month_key(d.year, d.month)
            if prev and key != _add_months(prev, 1):
                res['errors'].append('date column: %s follows %s (months must be consecutive)' % (key, prev))
                break
            prev, started = key, True
            vals = {}
            for field in FIELDS:
                v, prob = _value(r[col[field]] if col[field] < len(r) else None,
                                 'count' if field in COUNT_FIELDS else 'median')
                if prob:
                    res['errors'].append('%s %s: %s' % (key, field, prob))
                vals[field] = v
            res['months'][key] = vals
        elif started:
            break
    if not res['months']:
        res['errors'].append('no monthly rows found')
        return res
    with_data = [k for k, v in res['months'].items() if any(v[f] is not None for f in FIELDS)]
    if not with_data:
        res['errors'].append('no housing values in any month')
        return res
    first, last = min(with_data), max(with_data)
    res['months'] = {k: v for k, v in res['months'].items() if first <= k <= last}
    res['first_month'], res['last_month'] = first, last
    return res


def parse_summary_workbook(data):
    """Published month, year-ago month and YTD housing values per geography (counties and STATE)."""
    wb = Workbook(data)
    out = {'sheets': {}, 'errors': [], 'warnings': []}
    for si, name in enumerate(wb.sheet_names):
        rows = wb.rows(si)
        if not rows:
            continue
        title = next((c for c in rows[0] if isinstance(c, str) and c.strip()), '')
        m = re.match(r'\s*MONTHLY ECONOMIC INDICATORS:\s*(HONOLULU|HAWAII|MAUI|KAUAI|STATE)?_\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})', title, re.I)
        n = re.search(r'\b(State|Hono|Hawaii|Maui|Kauai)\s*$', name or '', re.I)
        by_name = n and {'state': 'STATE', 'hono': 'HONOLULU'}.get(n.group(1).lower(), n.group(1).upper())
        if not m or not (m.group(1) or by_name):
            continue
        geo = m.group(1).upper() if m.group(1) else by_name
        if m.group(1) and by_name and by_name != geo:
            out['warnings'].append('%s: title names %s but sheet name suggests %s' % (name, geo, by_name))
        sheet = {'sheet': name, 'title': title.strip(), 'release_date': _parse_long_date(m.group(2)),
                 'geography_from': 'sheet title' if m.group(1) else 'sheet name (title omits the geography)'}
        hi = None
        for i, r in enumerate(rows[:10]):
            cells = [str(c).strip() for c in r if isinstance(c, str)]
            if any(re.match(r'January \d{4} through [A-Za-z]+ \d{4} YTD$', c) for c in cells):
                hi = i
                break
        if hi is None:
            out['errors'].append('%s: YTD header row not found' % name)
            continue
        h = rows[hi]
        mcols, ycols = [], []
        for j, c in enumerate(h):
            if not isinstance(c, str):
                continue
            mm = re.match(r'^([A-Za-z]+) (\d{4})$', c.strip())
            yy = re.match(r'^January (\d{4}) through ([A-Za-z]+) (\d{4}) YTD$', c.strip())
            if mm and _parse_month_name(mm.group(1)):
                mcols.append((_month_key(int(mm.group(2)), _parse_month_name(mm.group(1))), j))
            elif yy and _parse_month_name(yy.group(2)):
                ycols.append((_month_key(int(yy.group(3)), _parse_month_name(yy.group(2))), j))
        if len(mcols) != 2 or len(ycols) != 2:
            out['errors'].append('%s: expected two month and two YTD columns, found %d and %d' % (name, len(mcols), len(ycols)))
            continue
        (ago, ago_j), (cur, cur_j) = sorted(mcols)
        (ytd_ago, ytd_ago_j), (ytd_cur, ytd_cur_j) = sorted(ycols)
        sheet.update(month=cur, year_ago_month=ago, ytd_through=ytd_cur, ytd_year_ago_through=ytd_ago, values={})
        labels = [(_norm(r[0]) if r else '') for r in rows]
        start = next((i for i, l in enumerate(labels) if l.startswith(SUMMARY_LABELS[0][1])), None)
        if start is None:
            out['errors'].append('%s: housing rows not found' % name)
            continue
        i = start
        for field, label in SUMMARY_LABELS:
            while i < len(labels) and not labels[i].startswith(label):
                i += 1
            if i >= len(labels) or i - start > 8:
                out['errors'].append('%s: row %r not found after resales row' % (name, label))
                break
            r = rows[i]
            kind = 'count' if field in COUNT_FIELDS else 'median'
            vals = {}
            for key, j in (('year_ago_month', ago_j), ('month', cur_j), ('ytd_year_ago', ytd_ago_j), ('ytd', ytd_cur_j)):
                v, prob = _value(r[j] if j < len(r) else None, kind)
                if prob:
                    out['errors'].append('%s %s %s: %s' % (name, field, key, prob))
                vals[key] = v
            sheet['values'][field] = vals
            i += 1
        out['sheets'][geo] = sheet
    return out


# ----------------------------------------------------------------- derived (counts only)
def compute_ytd(months, through_month):
    """YTD count sums per year; a field's sum is None unless January..through are all present."""
    years = sorted({k[:4] for k in months})
    out = {}
    for y in years:
        through = through_month if y == through_month[:4] else y + '-12'
        if through > through_month:
            continue
        span = [_month_key(int(y), m) for m in range(1, int(through[5:7]) + 1)]
        entry = {'through': through}
        for f in COUNT_FIELDS:
            vals = [months.get(k, {}).get(f) for k in span]
            missing = [k for k, v in zip(span, vals) if v is None]
            if all(v is None for v in vals):
                continue
            entry[f] = ({'value': sum(vals), 'complete': True, 'months': len(span)} if not missing else
                        {'value': None, 'complete': False, 'missing_months': missing})
        if len(entry) > 1:
            out[y] = entry
    return out


def ytd_same_months(months, through_month):
    """Current-year YTD and the prior year through the same month (both counts only)."""
    def block(through):
        span = [_month_key(int(through[:4]), m) for m in range(1, int(through[5:7]) + 1)]
        b = {'through': through}
        for f in COUNT_FIELDS:
            vals = [months.get(k, {}).get(f) for k in span]
            missing = [k for k, v in zip(span, vals) if v is None]
            b[f] = ({'value': sum(vals), 'complete': True, 'months': len(span)} if not missing else
                    {'value': None, 'complete': False, 'missing_months': missing})
        return b
    return {'current': block(through_month), 'prior_year_same_months': block(_add_months(through_month, -12))}


def ytd_gap_limit(published):
    """Largest accepted shortfall of the monthly rows against DBEDT's published YTD (late-reported sales)."""
    return max(5, round(0.03 * published))


def small_sample_flags(vals):
    return [m for m, n in MEDIAN_OF.items() if vals.get(m) is not None and vals.get(n) is not None and vals[n] < SMALL_N]


# ----------------------------------------------------------------- comparison
def diff_counties(old, new, until=None):
    """Changed/removed values for months present in both; new months listed separately."""
    changes, overlap, new_months = [], 0, set()
    for c in COUNTIES:
        om, nm = (old or {}).get(c, {}), (new or {}).get(c, {})
        for k in sorted(nm):
            if until and k > until:
                continue
            if k not in om:
                new_months.add(k)
                continue
            for f in FIELDS:
                a, b = om[k].get(f), nm[k].get(f)
                if a is not None:
                    overlap += 1
                if a == b:
                    continue
                kind = 'changed' if a is not None and b is not None else ('removed' if b is None else 'added')
                changes.append({'county': c, 'month': k, 'field': f, 'old': a, 'new': b, 'kind': kind})
    return changes, overlap, sorted(new_months)


def mass_revision(changes, overlap):
    n = sum(1 for x in changes if x['kind'] in ('changed', 'removed'))
    return n > MASS_REVISION_MIN and n > MASS_REVISION_SHARE * max(overlap, 1)


# ----------------------------------------------------------------- one run
def _store_raw(state_dir, res, ext):
    digest = sha256(res.data)
    raw_dir = os.path.join(state_dir, 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, digest + ext)
    if not os.path.exists(path):
        with open(path + '.tmp', 'wb') as f:
            f.write(res.data)
        os.replace(path + '.tmp', path)
    with open(os.path.join(raw_dir, 'MANIFEST.tsv'), 'a', encoding='utf-8') as f:
        f.write('\t'.join([res.retrieved_utc, str(res.status), str(len(res.data)), digest,
                           res.headers.get('last-modified', ''), res.final_url]) + '\n')
    return digest


def _source(role, res, digest, **extra):
    s = {'role': role, 'url': res.url, 'retrieved_utc': res.retrieved_utc, 'http_status': res.status,
         'bytes': len(res.data), 'sha256': digest,
         'http_last_modified': res.headers.get('last-modified'),
         'http_last_modified_note': 'server metadata; not a publication date'}
    if res.final_url != res.url:
        s['final_url'] = res.final_url
    s.update(extra)
    return s


def run(fetcher, state_dir, baseline=None, now=None, hold_on_revision=False, accept_mass_revision=False,
        page_url=PUBLISHER_PAGE):
    """One refresh. Returns the run record; it is also written to state_dir/runs/."""
    now = now or utc_now()
    checks = []
    rec = {'dataset': DATASET_ID, 'schema_version': SCHEMA_VERSION, 'run_utc': now, 'checks': checks}
    last_path = os.path.join(state_dir, 'last_good', DATASET_FILE)
    previous = read_json(last_path)
    rec['last_good_before'] = previous and {'release_id': previous['release']['release_id'],
                                            'observation_month': previous['release']['observation_month']}

    def finish(decision, exit_code, candidate=None, folder=None):
        rec['decision'], rec['exit_code'] = decision, exit_code
        rec['last_good_after'] = rec['last_good_before']
        if candidate is not None and folder:
            p = os.path.join(state_dir, folder, candidate['release']['release_id'] + '.json')
            write_json_atomic(p, candidate)
            rec['candidate_file'] = os.path.relpath(p, state_dir)
        if decision in ('promoted', 'promoted_republication'):
            write_json_atomic(last_path, candidate)
            write_json_atomic(os.path.join(state_dir, 'last_good', LATEST_FILE), latest_view(candidate))
            rec['last_good_after'] = {'release_id': candidate['release']['release_id'],
                                      'observation_month': candidate['release']['observation_month']}
        rec['kept_previous_last_good'] = rec['last_good_after'] == rec['last_good_before']
        stamp = re.sub(r'[^0-9TZ]', '', now)
        write_json_atomic(os.path.join(state_dir, 'runs', stamp + '.json'), rec)
        return rec

    # 1. publisher page and discovery
    page = fetcher.get(page_url)
    if not check(checks, 'fetch.publisher_page', page.ok, '%s -> %s' % (page_url, page.error or page.status)):
        return finish('fetch_failed', 3)
    page_digest = _store_raw(state_dir, page, '.html')
    disc = discover(page.data.decode('utf-8', errors='replace'), page_url)
    rec['discovery'] = {k: disc[k] for k in ('latest_complete_period', 'latest_listed_period', 'page_statements', 'problems')}
    period = disc['latest_complete_period']
    if not check(checks, 'discovery.county_workbooks', period is not None,
                 'latest period with all four county workbooks: %s; listed: %s' % (period, sorted(disc['periods']))):
        return finish('discovery_failed', 3)
    check(checks, 'discovery.latest_listed_is_complete', disc['latest_listed_period'] == period,
          'newest listed period %s; newest complete period %s' % (disc['latest_listed_period'], period), level='warn')
    for c in COUNTIES:
        lt = disc['periods'][period][c]['link_text'].lower().replace('ʻ', '')
        check(checks, 'discovery.link_text.%s' % c, c in lt, 'link text %r' % disc['periods'][period][c]['link_text'], level='warn')
    for p in disc['problems']:
        check(checks, 'discovery.problem', False, p, level='warn')
    if previous and period < previous['release']['observation_month']:
        check(checks, 'release.not_older_than_last_good', False,
              'publisher page lists %s; last good is %s' % (period, previous['release']['observation_month']))
        return finish('older_than_last_good', 2)

    # 2. fetch and parse the four county workbooks
    sources = [_source('publisher_page', page, page_digest)]
    parsed, fetch_failed, parse_failed = {}, False, False
    for c in COUNTIES:
        info = disc['periods'][period][c]
        res = fetcher.get(info['url'])
        if not check(checks, 'fetch.county.%s' % c, res.ok, '%s -> %s' % (info['url'], res.error or res.status)):
            fetch_failed = True
            continue
        digest = _store_raw(state_dir, res, '.xlsx')
        try:
            p = parse_county_workbook(res.data, c)
        except XlsxError as e:
            check(checks, 'parse.county.%s' % c, False, 'unreadable workbook: %s' % e)
            parse_failed = True
            continue
        sources.append(_source('county_workbook', res, digest, county=c, link_text=info['link_text'],
                               sheet=p['sheet'], title=p['title']))
        parse_failed |= not check(checks, 'parse.county.%s' % c, not p['errors'],
                                  '; '.join(p['errors'][:5]) or 'columns %s; months %s to %s' % (
                                      p.get('columns'), p.get('first_month'), p.get('last_month')))
        parsed[c] = p
    if fetch_failed:
        return finish('fetch_failed', 3)
    if parse_failed:
        return finish('validation_failed', 2)

    # 3. summary workbook (cross-check only; absence is a warning)
    summary = None
    sinfo = disc['summaries'].get(period)
    if check(checks, 'discovery.summary_workbook', sinfo is not None, 'summary workbook for %s: %s' % (
            period, sinfo and sinfo['url']), level='warn'):
        sres = fetcher.get(sinfo['url'])
        if check(checks, 'fetch.summary', sres.ok, '%s -> %s' % (sinfo['url'], sres.error or sres.status), level='warn'):
            sdig = _store_raw(state_dir, sres, '.xlsx')
            sources.append(_source('summary_workbook', sres, sdig, link_text=sinfo['link_text'],
                                   file_suffix=sinfo['file_suffix']))
            try:
                summary = parse_summary_workbook(sres.data)
                if not check(checks, 'parse.summary', not summary['errors'], '; '.join(summary['errors'][:5]) or
                             'sheets: %s' % sorted(summary['sheets']), level='warn'):
                    summary = None  # cross-checks skipped; the county data is validated on its own
            except XlsxError as e:
                check(checks, 'parse.summary', False, 'unreadable summary workbook: %s' % e, level='warn')

    # 4. release identity and validation of the county data
    county_digests = sorted(s['sha256'] for s in sources if s['role'] in ('county_workbook', 'summary_workbook'))
    release_id = '%s_%s' % (period, sha256(''.join(county_digests).encode())[:12])
    for c in COUNTIES:
        p = parsed[c]
        check(checks, 'release.title_period.%s' % c, p['through'] == period,
              'workbook title says through %s; file name says %s' % (p['through'], period))
        check(checks, 'release.last_month.%s' % c, p['last_month'] == period,
              'last month with housing data %s; release period %s' % (p['last_month'], period), level='incomplete')
        latest = p['months'].get(period, {})
        missing = [f for f in FIELDS if latest.get(f) is None]
        check(checks, 'complete.%s' % c, not missing, 'missing for %s: %s' % (period, missing or 'none'), level='incomplete')
        for k, v in p['months'].items():
            for f in COUNT_FIELDS:
                if v[f] is not None and v[f] > MAX_MONTHLY_COUNT:
                    check(checks, 'plausible.count', False, '%s %s %s = %s' % (c, k, f, v[f]), level='warn')
            for f in MEDIAN_OF:
                if v[f] is not None and not (MEDIAN_RANGE[0] <= v[f] <= MEDIAN_RANGE[1]):
                    check(checks, 'plausible.median', False, '%s %s %s = %s' % (c, k, f, v[f]), level='warn')
    released = sorted({p['released_on'] for p in parsed.values()}, key=str)
    released_s = sorted({s['release_date'] for s in summary['sheets'].values()}, key=str) if summary else []
    pub_statements = {'county_workbook_titles': released, 'summary_sheet_titles': released_s}
    pub_date, pub_basis = None, None
    if len(released) == 1 and released[0] and (not summary or released_s == released):
        pub_date = released[0]
        pub_basis = ('stated in all four county workbook titles ("was released on ...")' +
                     (' and in every summary sheet title' if summary else ''))
    check(checks, 'release.publication_date_established', pub_date is not None,
          'county workbook titles %s; summary sheet titles %s%s' % (
              released, released_s, '' if pub_date else ' (they disagree, so no publication date is set)'), level='warn')

    # 5. cross-check against DBEDT's own summary workbook
    months = {c: parsed[c]['months'] for c in COUNTIES}
    ytd = {c: compute_ytd(months[c], period) for c in COUNTIES}
    ytd_cmp = {c: ytd_same_months(months[c], period) for c in COUNTIES}
    published, ytd_gaps = None, []
    if summary:
        published = {}
        for c in COUNTIES + ('state',):
            geo = 'STATE' if c == 'state' else COUNTY_META[c]['summary_geo']
            sh = summary['sheets'].get(geo)
            if not check(checks, 'summary.sheet.%s' % c, sh is not None, 'summary sheet for %s' % geo, level='warn'):
                continue
            if not check(checks, 'summary.period.%s' % c, sh['month'] == period and sh['ytd_through'] == period,
                         'summary month %s, YTD through %s; release %s' % (sh['month'], sh['ytd_through'], period),
                         level='warn'):
                continue
            published[c] = {'month': sh['month'], 'year_ago_month': sh['year_ago_month'], 'ytd_through': sh['ytd_through'],
                            'values': sh['values'], 'sheet': sh['sheet']}
            if c == 'state':
                for f in COUNT_FIELDS:
                    tot = [months[x].get(period, {}).get(f) for x in COUNTIES]
                    s = sum(tot) if None not in tot else None
                    check(checks, 'summary.state_month_sum.%s' % f, s == sh['values'][f]['month'],
                          'sum of counties %s; DBEDT state %s' % (s, sh['values'][f]['month']), level='warn')
                    ys = [((summary['sheets'].get(COUNTY_META[x]['summary_geo']) or {}).get('values') or {}).get(f, {}).get('ytd')
                          for x in COUNTIES]
                    ys = sum(ys) if None not in ys else None
                    check(checks, 'summary.state_ytd_sum.%s' % f, ys == sh['values'][f]['ytd'],
                          'sum of county published YTD %s; DBEDT state YTD %s' % (ys, sh['values'][f]['ytd']), level='warn')
                for f in MEDIAN_OF:
                    check(checks, 'summary.state_median_not_published.%s' % f, sh['values'][f]['month'] is None,
                          'DBEDT state %s: %r (recorded as published; never derived)' % (f, sh['values'][f]['month']),
                          level='warn')
                continue
            for f in FIELDS:
                v = sh['values'][f]
                check(checks, 'summary.month.%s.%s' % (c, f), v['month'] == months[c].get(period, {}).get(f),
                      'summary %r vs county workbook %r (%s)' % (v['month'], months[c].get(period, {}).get(f), period))
                check(checks, 'summary.year_ago.%s.%s' % (c, f),
                      v['year_ago_month'] == months[c].get(sh['year_ago_month'], {}).get(f),
                      'summary %r vs county workbook %r (%s); the county workbook value is kept' % (
                          v['year_ago_month'], months[c].get(sh['year_ago_month'], {}).get(f), sh['year_ago_month']),
                      level='warn')
            for f in COUNT_FIELDS:
                for key, blk in (('ytd', 'current'), ('ytd_year_ago', 'prior_year_same_months')):
                    mine = ytd_cmp[c][blk][f]
                    pub = sh['values'][f][key]
                    through = ytd_cmp[c][blk]['through']
                    if not mine['complete'] or pub is None:
                        check(checks, 'summary.%s.%s.%s' % (key, c, f), False, 'sum of months %r (missing %s); published %r' % (
                            mine['value'], mine.get('missing_months'), pub), level='warn')
                        continue
                    gap = pub - mine['value']
                    ytd_gaps.append({'county': c, 'field': f, 'through': through, 'published_ytd': pub,
                                     'sum_of_monthly_rows': mine['value'], 'difference': gap})
                    check(checks, 'summary.%s.%s.%s' % (key, c, f), 0 <= gap <= ytd_gap_limit(pub),
                          'published YTD %r; sum of monthly rows %r (through %s)%s' % (
                              pub, mine['value'], through,
                              '; published YTD includes sales reported after the monthly rows were compiled' if gap > 0 else ''),
                          level='warn')

    # 6. revisions: against the last-good dataset and the verified baseline
    prev_counties = previous and {c: previous['counties'][c]['months'] for c in COUNTIES}
    rev, overlap, new_months = diff_counties(prev_counties, months) if previous else ([], 0, [])
    base_counties = baseline and baseline['counties']
    brev, boverlap, _ = diff_counties(base_counties, months, until=baseline and baseline['through']) if baseline else ([], 0, [])
    if baseline:
        check(checks, 'baseline.no_mass_difference', accept_mass_revision or not mass_revision(brev, boverlap),
              '%d of %d verified baseline values differ (through %s)' % (len(brev), boverlap, baseline['through']))
    if previous:
        check(checks, 'revisions.no_mass_revision', accept_mass_revision or not mass_revision(rev, overlap),
              '%d of %d earlier values changed or removed since %s' % (
                  sum(1 for x in rev if x['kind'] != 'added'), overlap, previous['release']['release_id']))
    snapshot = baseline and baseline['through']
    for x in rev + brev:
        x['affects_report_snapshot'] = bool(snapshot and x['month'] <= snapshot)

    # 7. assemble the candidate
    counties_out = {}
    for c in COUNTIES:
        ms = {}
        for k, v in months[c].items():
            e = dict(v)
            fl = small_sample_flags(v)
            if fl:
                e['small_sample'] = fl
            ms[k] = e
        counties_out[c] = dict(COUNTY_META[c], first_month=parsed[c]['first_month'], last_month=parsed[c]['last_month'],
                               months=ms)
    all_months = sorted(set().union(*[months[c].keys() for c in COUNTIES]))
    state_counts = {}
    for k in all_months:
        row = {}
        for f in COUNT_FIELDS:
            vals = [months[c].get(k, {}).get(f) for c in COUNTIES]
            row[f] = sum(vals) if None not in vals else None
        if any(v is not None for v in row.values()):
            state_counts[k] = row
    statuses = {r['status'] for r in checks}
    status = 'fail' if 'fail' in statuses else ('incomplete' if 'incomplete' in statuses else 'pass')
    candidate = {
        'dataset': DATASET_ID, 'schema_version': SCHEMA_VERSION,
        'title': 'Hawaiʻi county home resales and median prices, monthly (DBEDT Monthly Economic Indicators)',
        'publisher': 'State of Hawaiʻi DBEDT, Research and Economic Analysis Division',
        'publisher_page': page_url,
        'refresh_class': 'PUBLISHER-TIMED, MONTHLY (not live): show "as of <observation month>" and the publication date',
        'release': {
            'release_id': release_id, 'observation_month': period,
            'edition_label': 'MEI through %s %s' % (MONTHS[int(period[5:7]) - 1].capitalize(), period[:4]),
            'publication_date': pub_date, 'publication_date_basis': pub_basis,
            'publication_date_statements': pub_statements,
            'update_statements': sorted({p['update_statement'] for p in parsed.values() if p['update_statement']}),
            'page_statements': disc['page_statements'],
            'summary_file_suffix': sinfo and sinfo['file_suffix'],
            'summary_file_suffix_note': 'DBEDT file-name suffix; its meaning is not stated on the publisher page',
            'retrieved_utc': now,
        },
        'sources': sources, 'methodology': METHODOLOGY, 'fields': FIELD_META,
        'counties': counties_out,
        'ytd_published': published and {c: {
            'through': published[c]['ytd_through'], 'prior_year_through': _add_months(published[c]['ytd_through'], -12),
            'current': {f: published[c]['values'][f]['ytd'] for f in FIELDS},
            'prior_year_same_months': {f: published[c]['values'][f]['ytd_year_ago'] for f in FIELDS},
        } for c in COUNTIES if c in published},
        'ytd_published_note': ('DBEDT\'s own YTD counts and YTD medians from its summary workbook (canonical for YTD display). '
                               'For the current year they can exceed the sum of the monthly rows because they include sales '
                               'reported late; the prior year\'s monthly rows have been updated and match.'),
        'ytd_sum_of_monthly_counts': ytd, 'ytd_sum_same_months': ytd_cmp,
        'ytd_published_vs_sum_of_months': ytd_gaps,
        'state_counts': {'basis': METHODOLOGY['state_counts'], 'months': state_counts},
        'statewide_median': None,
        'statewide_median_note': 'DBEDT publishes no statewide median ("(NA)"); none is derived from county medians.',
        'published_summary': published,
        'validation': {'status': status, 'checks': checks},
        'revisions': {'vs_last_good': rev, 'vs_verified_baseline': brev, 'new_months': new_months,
                      'compared_with': previous and previous['release']['release_id'],
                      'baseline_through': baseline and baseline['through'],
                      'review_required': bool(rev)},
    }
    rec.update(release_id=release_id, observation_month=period, status=status, first_release=previous is None,
               new_months=new_months, revisions_vs_last_good=len(rev), differences_vs_baseline=len(brev))

    if status == 'fail':
        return finish('validation_failed', 2, candidate, 'rejected')
    if status == 'incomplete':
        return finish('incomplete', 2, candidate, 'rejected')
    if previous and previous['release']['release_id'] == release_id:
        return finish('no_change', 0)
    if hold_on_revision and rev:
        return finish('staged_for_review', 0, candidate, 'staged')
    same_period = bool(previous) and previous['release']['observation_month'] == period
    return finish('promoted_republication' if same_period else 'promoted', 0, candidate, 'staged')


def latest_view(ds):
    """Small file for the site: the newest month, year-ago month and YTD per county."""
    period = ds['release']['observation_month']
    ago = _add_months(period, -12)
    out = {'dataset': ds['dataset'], 'schema_version': ds['schema_version'], 'refresh_class': ds['refresh_class'],
           'observation_month': period, 'publication_date': ds['release']['publication_date'],
           'retrieved_utc': ds['release']['retrieved_utc'], 'release_id': ds['release']['release_id'],
           'page_statements': ds['release']['page_statements'], 'validation_status': ds['validation']['status'],
           'statewide_median': None, 'statewide_median_note': ds['statewide_median_note'],
           'revisions_in_this_release': ds['revisions']['vs_last_good'],
           'ytd_note': ds['ytd_published_note'], 'counties': {}}
    for c in COUNTIES:
        m = ds['counties'][c]['months']
        yp = (ds.get('ytd_published') or {}).get(c)
        out['counties'][c] = {
            'name': ds['counties'][c]['name'],
            'month': m.get(period), 'year_ago_month': m.get(ago),
            'ytd_published': yp,
            'ytd_sum_of_monthly_counts': ds['ytd_sum_same_months'][c],
        }
    out['state_counts'] = {'month': ds['state_counts']['months'].get(period),
                           'year_ago_month': ds['state_counts']['months'].get(ago)}
    return out


def load_baseline(path):
    b = read_json(path)
    if not b:
        return None
    return {'through': b['through'], 'counties': b['counties']}
