"""Check archived report integrity, accounting and portable output."""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/leverage/scripts'))
from report_data import require, validate_summary
from archive_report import refs_digest


def check_archive(path):
    source = json.loads((path/'source.json').read_text())
    data = json.loads((path/'data/snapshot.json').read_text())
    require(source['schema_version'] == 'leverage-archive/v1', 'Unknown provenance schema')
    require(data['schema_version'] == 'leverage-skill/v1', 'Unknown snapshot schema')
    require(data['contributors_complete'], 'Archive must retain every collected contributor')
    validate_summary(data['summary'])
    require(sum(row['lines'] for row in data['contributors']) == data['summary']['buckets']['contributors']['lines'], 'Contributor line accounting differs')
    for key in ('revision', 'status', 'tools', 'dirty', 'shallow', 'effort_method'):
        require(source[key] == data[key], f'Provenance differs: {key}')
    require(source['measurement_date'] == data['generated_at'], 'Measurement date differs')
    for key, value in source['fingerprints'].items():
        require(data[key] == value, 'Fingerprint differs')
    for name, digest in source['artifact_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Artifact escapes archive')
        require(hashlib.sha256((path/name).read_bytes()).hexdigest() == digest, f'Artifact changed: {name}')
    for config in source['config_sources']:
        require(not Path(config['path']).is_absolute() and '..' not in Path(config['path']).parts, 'Configuration has a host path')
    if source.get('ref_manifest'):
        require(source['ref_manifest'] == 'refs.txt', 'Unexpected ref manifest')
        require(refs_digest((path/'refs.txt').read_text()) == data['refs_digest'], 'Ref manifest differs')
    if source['scope_override']:
        require(source['scope_override'] == 'scope/.sccignore', 'Unexpected scope override')
        digest = hashlib.sha256((path/source['scope_override']).read_bytes()).hexdigest()
        require(any(c['path'] == '.sccignore' and c['sha256'] == digest for c in source['config_sources']), 'Scope override differs from measured input')
    with (path/'data/contributors.csv').open() as stream:
        csv_rows = list(csv.DictReader(stream))
    by_id = {row['row_id']: row for row in csv_rows}
    require(len(by_id) == len(csv_rows) == len(data['contributors']), 'CSV identities differ')
    for row in data['contributors']:
        csv_row = by_id[row['row_id']]
        expected_name = ("'" if row['name'].startswith(('=', '+', '-', '@')) else '') + row['name']
        require(csv_row['name'] == expected_name, 'CSV display name differs')
        for key in ('lines', 'share', 'estimated_person_months', 'elapsed_person_months', 'leverage'):
            value = None if csv_row[key] == '' else float(csv_row[key])
            require(value == row[key], f'CSV measurement differs: {key}')
        require(csv_row['history_complete'] == str(row['history_complete']), 'CSV history status differs')
    require(math.isclose(sum(r['estimated_person_months'] for r in data['contributors']),
                         data['summary']['buckets']['contributors']['estimated_person_months'], rel_tol=1e-8, abs_tol=1e-8),
            'Contributor effort accounting differs')
    ET.parse(path/'assets/contributors.svg')
    if (path/'assets/contributors.png').exists():
        require((path/'assets/contributors.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG')
    require(not (path/'raw').exists(), 'Raw captures do not belong in the archive')
    for file in path.rglob('*'):
        if file.is_file() and file.suffix != '.png':
            text = file.read_text()
            require(not any(prefix in text for prefix in ('/Users/', '/home/', 'file://')), f'Host path in {file.name}')
            require(not re.search(r'[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}', text), f'Email address in {file.name}')


def main():
    paths = sorted((ROOT/'reports').glob('*/*/source.json'))
    require(bool(paths), 'No reports found')
    for source in paths:
        check_archive(source.parent)
        print('Verified ' + str(source.parent.relative_to(ROOT)))


if __name__ == '__main__':
    main()
