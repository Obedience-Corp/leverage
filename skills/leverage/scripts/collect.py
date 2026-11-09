"""Collect scoped Camp reports and build a report bundle outside the source repo."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from bootstrap import capable
from render import write_bundle
from report_data import normalize, require


def command(args, **kwargs):
    # A process group allows cancellation to stop Camp's Git/scc children too.
    proc = subprocess.Popen([str(a) for a in args], start_new_session=os.name != 'nt', **kwargs)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        import signal
        if os.name != 'nt':
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait()
        raise


def collect(args):
    require(shutil.which('git'), 'Git is required; install it through your platform package manager')
    require(shutil.which('scc'), 'scc is required (for example: brew install scc, or the official scc releases)')
    target = args.target.expanduser().resolve()
    resolved = subprocess.run(['git', '-C', str(target), 'rev-parse', '--show-toplevel'],
                              capture_output=True, text=True, timeout=30)
    require(resolved.returncode == 0, 'Target must be inside a local Git working tree')
    root = Path(resolved.stdout.strip()).resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (args.output or root.parent / f'{root.name}-leverage-report-{stamp}').expanduser().resolve()
    require(not output.is_relative_to(root), 'Output must be outside the analyzed Git root')
    require(not output.exists(), 'Output already exists; choose a new directory')
    if args.camp:
        camp = args.camp.expanduser().resolve()
        require(capable(camp), '--camp executable lacks required leverage capabilities')
    else:
        helper = Path(__file__).with_name('ensure-festival.sh')
        ready = subprocess.run(['bash', str(helper)], capture_output=True, text=True)
        if ready.stderr:
            print(ready.stderr, file=sys.stderr, end='')
        require(ready.returncode == 0, 'Festival bootstrap was not ready; resolve the diagnostic above')
        camp = Path(ready.stdout.strip())
        require(camp.is_absolute() and capable(camp), 'Bootstrap did not return a capable absolute Camp path')
    raw = output / 'raw'
    raw.mkdir(parents=True)
    records, reports = [], {}
    views = ['personal'] if args.mode == 'personal' else ['repository']
    if args.mode in ('overview', 'contributors'):
        views.append('contributors')
    print(f'leverage: Saving report to {output}', file=sys.stderr)
    try:
        for view in views:
            argv = [str(camp), 'leverage', str(target), '--json']
            if view == 'contributors':
                argv += ['--by-author', '--author-threshold', '0']
            if view == 'personal':
                argv += ['--author', args.author]
            if view == 'repository' and args.people:
                argv += ['--people', str(args.people)]
            started = datetime.now(timezone.utc).isoformat()
            with (raw / f'{view}.json').open('w') as stdout, (raw / f'{view}.stderr').open('w') as stderr:
                code = command(argv, stdout=stdout, stderr=stderr)
            records.append({'view': view, 'argv': argv, 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': code})
            diagnostic = (raw / f'{view}.stderr').read_text()
            if code not in (0, 2):
                raise ValueError(f'Camp {view} failed with exit {code}: {diagnostic.strip()}')
            result = json.loads((raw / f'{view}.json').read_text())
            require(code != 2 or result.get('status') == 'partial', 'Exit 2 did not contain a partial Camp report')
            require(code != 0 or result.get('status') in ('complete', 'empty'), 'Camp exit/status mismatch')
            reports[view] = result
        data = normalize(**reports)
        write_bundle(data, output, args.top, args.sort, args.theme, args.png)
        print(output / 'report.md')
        return 2 if data['status'] == 'partial' else 0
    finally:
        (raw / 'collection.json').write_text(json.dumps({'camp': str(camp), 'target': str(target), 'commands': records}, indent=2) + '\n')
        (raw / 'diagnostics.txt').write_text('\n'.join(p.read_text() for p in sorted(raw.glob('*.stderr'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path, nargs='?', default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--camp', type=Path, help='use an explicitly verified Camp executable instead of bootstrap')
    parser.add_argument('--mode', choices=('overview', 'summary', 'personal', 'contributors'), default='overview')
    parser.add_argument('--author')
    parser.add_argument('--people', type=int)
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--sort', choices=('ownership', 'ratio'), default='ownership')
    parser.add_argument('--theme', choices=('dark', 'light'), default='dark')
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args()
    try:
        require((args.mode == 'personal') == bool(args.author), '--author is required only for personal mode')
        require(args.people is None or args.people > 0, '--people must be positive')
        require(not args.people or args.mode != 'personal', '--people is unavailable in personal mode')
        require(1 <= args.top <= 1000, '--top must be from 1 to 1000')
        return collect(args)
    except KeyboardInterrupt:
        print('leverage: Canceled; completed raw captures remain in the output directory.', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('leverage: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
