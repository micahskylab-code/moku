"""Dependency-free reader for the cached cell values in .xlsx workbooks.

Reads shared strings, inline strings, numbers, booleans and error codes from
each worksheet. Formulas are not evaluated: the value Excel cached when the
file was saved is used, which is what DBEDT publishes. Styles are ignored, so
dates come back as Excel serial numbers; convert them with excel_serial_to_date.
"""
import datetime
import io
import re
import zipfile
import xml.etree.ElementTree as ET

NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
_M = '{%s}' % NS_MAIN
_INT_RE = re.compile(r'^-?\d+$')


class XlsxError(ValueError):
    """The bytes are not a readable .xlsx workbook."""


def _col_index(ref):
    """'AO44' -> 40 (0-based column)."""
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    if n == 0:
        raise XlsxError('bad cell reference %r' % ref)
    return n - 1


def _row_number(ref):
    digits = ''.join(ch for ch in ref if ch.isdigit())
    return int(digits) if digits else None


def _text(el):
    """Text of a shared-string or inline-string item, skipping phonetic runs."""
    if el is None:
        return ''
    t = el.find(_M + 't')
    if t is not None:
        return t.text or ''
    return ''.join((r.findtext(_M + 't') or '') for r in el.findall(_M + 'r'))


def _number(s):
    s = s.strip()
    if _INT_RE.match(s):
        return int(s)
    return float(s)


def excel_serial_to_date(serial, date1904=False):
    """Excel serial day number -> datetime.date (1900 or 1904 date system)."""
    if date1904:
        return datetime.date(1904, 1, 1) + datetime.timedelta(days=int(serial))
    if serial < 61:  # Excel's fictitious 1900-02-29; DBEDT data starts in 1990
        raise XlsxError('serial %r predates supported range' % serial)
    return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(serial))


class Workbook:
    def __init__(self, data):
        if not isinstance(data, (bytes, bytearray)) or not data[:2] == b'PK':
            raise XlsxError('not an .xlsx (zip) file')
        try:
            self._z = zipfile.ZipFile(io.BytesIO(data))
            names = set(self._z.namelist())
            wb = ET.fromstring(self._z.read('xl/workbook.xml'))
            rels = ET.fromstring(self._z.read('xl/_rels/workbook.xml.rels'))
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
            raise XlsxError('unreadable workbook: %s' % e)
        pr = wb.find(_M + 'workbookPr')
        self.date1904 = pr is not None and pr.get('date1904') in ('1', 'true')
        target = {r.get('Id'): r.get('Target') for r in rels.findall('{%s}Relationship' % NS_PKG_REL)}
        self.sheets = []
        for s in wb.iter(_M + 'sheet'):
            t = target.get(s.get('{%s}id' % NS_DOC_REL))
            if not t:
                continue
            path = t.lstrip('/') if t.startswith('/') else 'xl/' + t
            self.sheets.append((s.get('name'), path))
        if not self.sheets:
            raise XlsxError('workbook lists no worksheets')
        self._shared = []
        if 'xl/sharedStrings.xml' in names:
            sst = ET.fromstring(self._z.read('xl/sharedStrings.xml'))
            self._shared = [_text(si) for si in sst.findall(_M + 'si')]

    @property
    def sheet_names(self):
        return [n for n, _ in self.sheets]

    def rows(self, sheet=0):
        """All rows of one sheet as dense lists (row 1 -> index 0); blank cells are None."""
        name, path = self.sheets[sheet] if isinstance(sheet, int) else next(
            (s for s in self.sheets if s[0] == sheet), (None, None))
        if path is None:
            raise XlsxError('no sheet %r' % sheet)
        try:
            root = ET.fromstring(self._z.read(path))
        except (KeyError, ET.ParseError) as e:
            raise XlsxError('unreadable sheet %r: %s' % (name, e))
        out = {}
        for row in root.iter(_M + 'row'):
            rn = row.get('r')
            cells = {}
            for c in row.findall(_M + 'c'):
                ref = c.get('r')
                if ref is None:
                    raise XlsxError('cell without reference in sheet %r' % name)
                if rn is None:
                    rn = str(_row_number(ref))
                t = c.get('t', 'n')
                v = c.findtext(_M + 'v')
                if t == 's':
                    val = self._shared[int(v)] if v is not None else None
                elif t == 'inlineStr':
                    val = _text(c.find(_M + 'is'))
                elif t in ('str', 'e'):
                    val = v
                elif t == 'b':
                    val = None if v is None else v.strip() == '1'
                else:
                    val = None if v is None or v.strip() == '' else _number(v)
                cells[_col_index(ref)] = val
            if rn is not None:
                out[int(rn)] = cells
        if not out:
            return []
        rows = []
        for r in range(1, max(out) + 1):
            cells = out.get(r, {})
            width = max(cells) + 1 if cells else 0
            rows.append([cells.get(i) for i in range(width)])
        return rows
