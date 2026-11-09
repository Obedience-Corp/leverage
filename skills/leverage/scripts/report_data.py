"""Normalize Camp v1 reports without recomputing scores."""
import hashlib
import math
from pathlib import Path

BUCKETS = ('contributors', 'excluded_identities', 'uncommitted', 'unavailable')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(value, name, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, f'Invalid {name}')
    return value


def validate_summary(summary):
    for key in ('files', 'lines', 'code_lines', 'estimated_person_months'):
        numeric(summary[key], key)
    require(summary['code_lines'] <= summary['lines'], 'Code lines exceed physical lines')
    buckets = summary['buckets']
    require(set(buckets) == set(BUCKETS), 'Missing/unknown accounting buckets')
    for key, bucket in buckets.items():
        for field in ('lines', 'share', 'estimated_person_months'):
            numeric(bucket[field], key + '.' + field)
        require(bucket['share'] <= 1, 'Share exceeds 100%')
        expected = bucket['lines'] / summary['lines'] if summary['lines'] else 0
        require(math.isclose(bucket['share'], expected, abs_tol=1e-8), 'Bucket share mismatch')
    require(sum(b['lines'] for b in buckets.values()) == summary['lines'], 'Accounting lines do not reconcile')
    require(math.isclose(sum(b['estimated_person_months'] for b in buckets.values()),
                         summary['estimated_person_months'], rel_tol=1e-8, abs_tol=1e-8), 'Estimated allocations do not reconcile')


def scope_of(report):
    if report.get('schema_version') == 'leverage-contributors/v1':
        require(len(report['projects']) == 1, 'Select one Git repository for this skill report')
        return report['projects'][0]
    if report.get('schema_version') == 'leverage-repository/v1':
        return report['report']['scope']
    raise ValueError('Unsupported Camp report schema; use a compatible Camp version')


def same_scope(a, b):
    for key in ('target', 'git_root', 'head', 'manifest_digest', 'content_digest', 'identity_digest', 'refs_digest',
                'files', 'lines', 'code_lines', 'estimated_person_months', 'config_sources', 'scan_arguments'):
        require(a.get(key) == b.get(key), f'Reports have different scope/inputs: {key}')


def normalize(repository=None, contributors=None, personal=None):
    reports = [r for r in (repository, contributors, personal) if r is not None]
    require(bool(reports), 'Supply at least one Camp report')
    scopes = [scope_of(r) for r in reports]
    for r in reports:
        require(r.get('status') in ('complete', 'partial', 'empty'), 'Invalid report status')
    for scope in scopes[1:]:
        same_scope(scopes[0], scope)
    reference_tools = reports[0].get('tools', reports[0].get('report', {}).get('tools'))
    for r in reports[1:]:
        require(reference_tools == r.get('tools', r.get('report', {}).get('tools')), 'Reports used different tool versions')
    scope = scopes[0]
    source = contributors or repository or personal
    meta = source if source is contributors else source['report']
    summary = meta['summary']
    validate_summary(summary)
    for key in ('files', 'lines', 'code_lines', 'estimated_person_months'):
        require(summary[key] == scope[key], f'Summary/scope mismatch: {key}')
    rows, ids = [], set()
    if contributors is not None:
        require(contributors.get('method') == 'contributor_worktree_v1', 'Unsupported contributor method')
        for row in contributors['contributors']:
            require(row['id'] not in ids, 'Duplicate contributor identity')
            ids.add(row['id'])
            for key in ('lines', 'share', 'estimated_person_months', 'elapsed_person_months', 'leverage'):
                numeric(row[key], 'contributor.' + key, nullable=key in ('elapsed_person_months', 'leverage'))
            expected = row['lines'] / summary['lines'] if summary['lines'] else 0
            require(math.isclose(expected, row['share'], abs_tol=1e-8), 'Contributor share mismatch')
            public_id = hashlib.sha256(row['id'].encode()).hexdigest()[:16]
            name = str(row['name']).strip()
            if '@' in name or not name:
                name = 'Contributor ' + public_id[:8]
            rows.append({**{k: row[k] for k in ('lines', 'share', 'estimated_person_months', 'elapsed_person_months', 'leverage')},
                         'row_id': public_id, 'name': name, 'history_complete': bool(row['history_complete'])})
        omitted = contributors['display']['omitted_lines']
        if contributors['display']['omitted_contributors'] == 0:
            require(math.isclose(sum(row['estimated_person_months'] for row in rows),
                                 summary['buckets']['contributors']['estimated_person_months'],
                                 rel_tol=1e-8, abs_tol=1e-8), 'Contributor estimated allocations do not reconcile')
        numeric(omitted, 'omitted_lines')
        require(sum(r['lines'] for r in rows) + omitted == summary['buckets']['contributors']['lines'], 'Contributor rows do not reconcile with accounting')
    statuses = {r['status'] for r in reports}
    status = 'partial' if 'partial' in statuses else ('empty' if 'empty' in statuses else 'complete')
    diagnostics = sorted({d['code'] for r in reports for d in r.get('diagnostics', r.get('report', {}).get('diagnostics', []))})
    score = personal or repository
    return {
        'schema_version': 'leverage-skill/v1', 'status': status,
        'repository': Path(scope['target']).name, 'revision': scope.get('head'),
        'generated_at': meta['generated_at'], 'tools': meta['tools'],
        'manifest_digest': scope['manifest_digest'], 'content_digest': scope['content_digest'],
        'identity_digest': scope.get('identity_digest'), 'refs_digest': scope.get('refs_digest'),
        'dirty': scope.get('dirty'), 'shallow': scope.get('shallow'),
        'config_sources': [{'name': Path(c['path']).name, 'sha256': c['sha256']} for c in scope.get('config_sources', [])],
        'excluded_directories': [scope['scan_arguments'][i+1] for i, arg in enumerate(scope.get('scan_arguments', [])[:-1]) if arg == '--exclude-dir'],
        'summary': summary, 'contributors': rows,
        'contributors_collected': contributors is not None,
        'contributors_complete': contributors is not None and contributors['display']['omitted_contributors'] == 0,
        'omitted_contributors': contributors['display']['omitted_contributors'] if contributors else None,
        'score': {k: score['campaign'].get(k) for k in ('full_leverage', 'actual_person_months', 'estimated_people', 'estimated_months')} if score else None,
        'view': 'personal' if personal else ('overview' if repository and contributors else ('contributors' if contributors else 'summary')),
        'effort_method': score['report']['effort_method'] if score else 'repository_commit_span_v1',
        'matched_identities': len(personal['report']['matched_author_ids']) if personal else None,
        'diagnostic_codes': diagnostics,
    }
