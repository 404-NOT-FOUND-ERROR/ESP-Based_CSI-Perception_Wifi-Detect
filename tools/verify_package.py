#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify local documentation links, sample hashes and self-contained report data."""
import csv
import hashlib
import json
from pathlib import Path
import re


def main():
    root = Path(__file__).resolve().parents[1]
    markdown = [root / 'README.md', *root.glob('docs/*.md'), *root.glob('components/*/README.md'),
                root / 'components/app_csi_probe/POWER_POLICY.md', root / 'tools/radio_review/README.md']
    links = 0
    for document in markdown:
        for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
            if re.match(r'^(https?://|#)', target):
                continue
            assert (document.parent / target.split('#')[0]).exists(), (document, target)
            links += 1
    review = json.loads((root / 'examples/report/review.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'docs/source-manifest.json').read_text(encoding='utf-8'))
    for row in manifest['imported_files']:
        assert row['packaged_sha256'] == hashlib.sha256((root / row['destination_path']).read_bytes()).hexdigest()
    for report in review['reports']:
        fixture = root / 'fixtures' / report['source']['name']
        assert report['simulated'] is True
        assert report['source']['sha256'] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    html = (root / 'examples/report/report.html').read_text(encoding='utf-8')
    payload = html.split('<script type="application/json" id="review-data">', 1)[1].split('</script>', 1)[0]
    assert json.loads(payload) == review
    with (root / 'examples/power-measurements.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream))
    assert len(rows) == 5 and all(len(row) == len(rows[0]) for row in rows)
    print(f'PASS {links} local links, {len(manifest["imported_files"])} packaged source hashes, '
          '2 simulated fixture hashes, embedded report, 4 planned power rows')


if __name__ == '__main__':
    main()
