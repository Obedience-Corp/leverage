"""Archive one real-repository report without raw identities or machine paths."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/leverage/scripts'))
from render import mdtext, write_bundle
from report_data import normalize, require, scope_of


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refs_digest(text):
    # Match Go encoding/json's string encoding used by Camp's scope fingerprint.
    encoded = json.dumps(text, ensure_ascii=False)
    for char, escaped in (('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')):
        encoded = encoded.replace(char, escaped)
    return hashlib.sha256(encoded.encode()).hexdigest()


def archive(repository, contributors, source, commit_date, destination, scope_file=None, png=False, refs_file=None):
    require(re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source),
            'Use the canonical HTTPS GitHub repository URL without a trailing slash')
    datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
    repo, authors = (json.loads(p.read_text()) for p in (repository, contributors))
    data = normalize(repository=repo, contributors=authors)
    require(data['contributors_complete'], 'Archive a threshold-zero contributor export')
    scope = scope_of(repo)
    require(re.fullmatch(r'[a-f0-9]{40}', data['revision'] or ''), 'A committed source revision is required')
    git_root = Path(scope['git_root'])
    target = Path(scope['target'])
    require(not destination.resolve().is_relative_to(git_root.resolve()), 'Archive outside the measured Git root')
    require(not destination.exists(), 'Archive destination already exists')
    configs = []
    for config in scope['config_sources']:
        # An external config needs an explicit portable representation before sharing.
        configs.append({'path': Path(config['path']).relative_to(git_root).as_posix(), 'sha256': config['sha256']})
    arguments = ['.' if arg == str(target) else arg for arg in scope['scan_arguments']]
    require(not any(Path(arg).is_absolute() for arg in arguments), 'Scan arguments contain a machine path')
    refs = refs_file.read_text() if refs_file else None
    if refs is not None:
        require(refs_digest(refs) == data['refs_digest'], 'Ref manifest differs from the measured Git refs')
    override = None
    if scope_file:
        digest = sha256(scope_file)
        matches = [c for c in scope['config_sources'] if Path(c['path']) == scope_file and c['sha256'] == digest]
        require(len(matches) == 1, 'Scope override does not match the measured configuration')
        require(scope_file.name == '.sccignore', 'Only .sccignore overrides are archived')
        override = scope_file.read_text()
    evidence = {
        'schema_version': 'leverage-archive/v1',
        'source_url': source, 'source_commit_date': commit_date,
        'measurement_date': data['generated_at'], 'revision': data['revision'],
        'target_subdirectory': target.relative_to(git_root).as_posix(),
        'status': data['status'], 'dirty': data['dirty'], 'shallow': data['shallow'],
        'method': authors['method'], 'history_method': authors['history_method'],
        'effort_method': data['effort_method'], 'tools': data['tools'],
        'fingerprints': {key: data[key] for key in ('manifest_digest', 'content_digest', 'identity_digest', 'refs_digest')},
        'config_sources': configs, 'scan_arguments': arguments,
        'input_sha256': {'repository.json': sha256(repository), 'contributors.json': sha256(contributors)},
        'scope_override': 'scope/.sccignore' if override is not None else None,
        'ref_manifest': 'refs.txt' if refs is not None else None,
    }
    write_bundle(data, destination, png=png)
    if override is not None:
        (destination/'scope').mkdir()
        (destination/'scope/.sccignore').write_text(override)
    if refs is not None:
        (destination/'refs.txt').write_text(refs)
    files = ('report.md', 'assets/contributors.svg', 'assets/contributors.png', 'data/contributors.csv', 'data/snapshot.json', 'refs.txt')
    evidence['artifact_sha256'] = {name: sha256(destination/name) for name in files if (destination/name).exists()}
    (destination/'source.json').write_text(json.dumps(evidence, indent=2) + '\n')
    revision_url = source + '/tree/' + data['revision']
    lines = [f"# {mdtext(data['repository'])}: measured snapshot", '',
             f"[Read the report](report.md) · [SVG](assets/contributors.svg) · [CSV](data/contributors.csv) · [Provenance](source.json)", '',
             f"Source: [{mdtext(source.removeprefix('https://github.com/'))}]({revision_url})", '',
             f"Revision: `{data['revision']}`. Source commit date: {commit_date}. Measurement generated: {data['generated_at']}.", '',
             f"Status: **{data['status']}**. Dirty: `{data['dirty']}`. Shallow: `{data['shallow']}`. Contributor export threshold: **0%**.", '',
             'The measurement date is not the source commit date. This is a pinned checkout snapshot, not a claim about the latest upstream code.', '',
             '## Scope and reproduction', '',
             'The exact scan arguments, configuration hashes, tool versions, history method and scope fingerprints are in `source.json`. Repository-relative configuration paths refer to files at the source revision. No additional generated/imported-code audit was performed.']
    if override is not None:
        lines += ['', 'This run used an extra `.sccignore`, preserved in [scope/.sccignore](scope/.sccignore). Apply that file at the checkout root before collecting. The recorded dirty state reflects that local override.']
    if refs is not None:
        lines += ['', 'The exact local ref names and commit IDs are preserved in [refs.txt](refs.txt); the archive verifies that they match the measured `refs_digest`. Recreate those refs in a separate full-history clone when attempting an exact historical rerun.']
    lines += ['', 'Use a full-history checkout at the recorded revision, matching configuration and tool versions, then run from the leverage repository:', '',
              '```sh', 'python3 skills/leverage/scripts/collect.py /path/to/source --output /path/outside/source/new-report --png', '```', '',
              'Camp uses all local Git refs for commit spans. Matching HEAD alone does not recreate the historical denominator: compare `refs_digest`, the other fingerprints and exact metrics before treating a new run as the same measurement. Fresh clones and later fetches can change those inputs.', '',
              'Original raw exports stay outside this archive because they include email identities and local paths. Their SHA-256 hashes identify the inputs; the portable snapshot and full CSV retain exact numeric values and display names. Hashes identify files, not independent proof of their authenticity.', '',
              'Calendar-span estimates do not measure actual hours or establish AI use. Contributor ratios must not be summed to reproduce the repository score.']
    (destination/'README.md').write_text('\n'.join(lines) + '\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--contributors', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--commit-date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scope-file', type=Path)
    parser.add_argument('--png', action='store_true')
    parser.add_argument('--refs-file', type=Path, help='exact git for-each-ref --format="%%(refname) %%(objectname)" output')
    args = parser.parse_args()
    try:
        archive(args.repository, args.contributors, args.source, args.commit_date, args.output, args.scope_file, args.png, args.refs_file)
        print(args.output/'README.md')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(1, f'archive: {error}\n')


if __name__ == '__main__':
    main()
