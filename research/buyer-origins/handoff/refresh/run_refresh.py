#!/usr/bin/env python3
"""Check DBEDT for a new Monthly Economic Indicators release and refresh the county housing dataset.

Usage:
  python3 run_refresh.py --state-dir PATH [--offline-dir PATH] [--now 2026-10-09T00:00:00Z]
                         [--baseline PATH] [--hold-on-revision] [--accept-mass-revision]

Exit codes:
  0  promoted a new release, promoted a same-period republication, staged for review, or no change
  2  validation failed, the latest month is incomplete, or the page lists an older release (last good kept)
  3  the publisher page or a workbook could not be fetched, or discovery failed (last good kept)
Prints the run record's summary as one JSON line. The full record is in STATE/runs/.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dbedt_mei  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--state-dir', required=True, help='folder for raw/, runs/, staged/, rejected/ and last_good/')
    ap.add_argument('--baseline', default=os.path.join(HERE, 'baseline', 'verified_2026-08.json'),
                    help='verified baseline to compare against (default: the report snapshot through 2026-08)')
    ap.add_argument('--no-baseline', action='store_true', help='skip the baseline comparison')
    ap.add_argument('--offline-dir', help='read the publisher page (mei_index.html) and workbooks from this folder instead of the web')
    ap.add_argument('--now', help='UTC timestamp to record for this run (for reproducible re-runs)')
    ap.add_argument('--hold-on-revision', action='store_true',
                    help='stage, but do not promote, a release that revises months already in the last-good dataset')
    ap.add_argument('--accept-mass-revision', action='store_true',
                    help='allow a release that changes many earlier values (normally treated as a layout change)')
    ap.add_argument('--user-agent', help='HTTP User-Agent (default: Python urllib)')
    ap.add_argument('--timeout', type=int, default=60)
    a = ap.parse_args(argv)

    now = a.now or dbedt_mei.utc_now()
    if a.offline_dir:
        fetcher = dbedt_mei.DirectoryFetcher(a.offline_dir, now=now)
    else:
        fetcher = dbedt_mei.HttpFetcher(timeout=a.timeout, user_agent=a.user_agent)
    baseline = None if a.no_baseline else dbedt_mei.load_baseline(a.baseline)
    rec = dbedt_mei.run(fetcher, os.path.abspath(a.state_dir), baseline=baseline, now=now,
                        hold_on_revision=a.hold_on_revision, accept_mass_revision=a.accept_mass_revision)
    problems = [c for c in rec['checks'] if c['status'] != 'pass']
    out = {k: rec.get(k) for k in ('run_utc', 'decision', 'exit_code', 'release_id', 'observation_month',
                                   'status', 'new_months', 'revisions_vs_last_good', 'last_good_after')}
    out['non_passing_checks'] = [(c['status'], c['id']) for c in problems]
    print(json.dumps(out, ensure_ascii=False))
    return rec['exit_code']


if __name__ == '__main__':
    sys.exit(main())
