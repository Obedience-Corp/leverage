"""Festival readiness for leverage. stdout is the verified Camp path only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.error
import time

REPO = 'Obedience-Corp/festival'
TIMEOUT = 120


class BootstrapError(Exception):
    def __init__(self, message, code=3):
        super().__init__(message)
        self.code = code


def say(message):
    print('leverage: ' + message, file=sys.stderr)


def run(args):
    try:
        return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                              timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(f'{args[0]}: {exc}') from exc


def capable(path):
    if not path or not Path(path).is_file():
        return False
    result = run([path, 'leverage', '--help'])
    return result.returncode == 0 and all(flag in result.stdout for flag in
                                        ('--dir', '--author', '--by-author', '--author-threshold', '--json'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def find_tool(name, install):
    found = shutil.which(name)
    if found:
        return Path(found).absolute()
    for directory in (install, Path.home() / '.obey/installer/bin'):
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.absolute()
    return None


def fetch(url):
    headers = {'User-Agent': 'Obedience-Corp-leverage'}
    if '/releases/assets/' in url:
        headers['Accept'] = 'application/octet-stream'
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (500, 502, 503, 504) or attempt == 2:
                raise BootstrapError(f'Download failed for {url}: {exc}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise BootstrapError(f'Download failed for {url}: {exc}') from exc
        time.sleep(attempt + 1)
    raise BootstrapError(f'Download failed for {url}')


def release_payload():
    metadata = json.loads(fetch(f'https://api.github.com/repos/{REPO}/releases/latest'))
    system = {'Darwin': 'macOS', 'Linux': 'linux'}.get(platform.system())
    arch = {'x86_64': 'x86_64', 'amd64': 'x86_64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
    if not system or not arch:
        raise BootstrapError('Automatic bootstrap supports macOS/Linux. On Windows use WSL2 or the documented Scoop route.')
    tag = metadata['tag_name']
    name = f'festival-{tag.removeprefix("v")}-{system}-{"all" if system == "macOS" else arch}.tar.gz'
    assets = {a['name']: a for a in metadata['assets']}
    def asset_url(name):
        asset = assets[name]
        api = asset.get('url', '')
        # Official asset API avoids release-page proxy failures, without a token.
        api_prefix = f'https://api.github.com/repos/{REPO}/releases/assets/'
        if api.startswith(api_prefix) and api.removeprefix(api_prefix).isdigit():
            return api
        return asset['browser_download_url']
    if name not in assets or 'checksums.txt' not in assets:
        raise BootstrapError(f'No supported release archive/checksums for {system}/{arch}.')
    prefix = f'https://github.com/{REPO}/releases/download/{tag}/'
    if any(not assets[n]['browser_download_url'].startswith(prefix) for n in (name, 'checksums.txt')):
        raise BootstrapError('Unexpected release download origin.')
    sums = fetch(asset_url('checksums.txt')).decode()
    expected = [line.split()[0] for line in sums.splitlines()
                if len(line.split()) == 2 and line.split()[1].lstrip('*') == name]
    if len(expected) != 1:
        raise BootstrapError('Release archive checksum is missing or ambiguous.')
    archive = fetch(asset_url(name))
    if hashlib.sha256(archive).hexdigest().lower() != expected[0].lower():
        raise BootstrapError('Festival archive checksum mismatch; nothing installed.')
    with tempfile.TemporaryFile() as stream:
        stream.write(archive)
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode='r:gz') as tar:
            result = {}
            for binary in ('camp', 'fest', 'festival'):
                members = [m for m in tar.getmembers() if Path(m.name).name == binary and m.isfile()]
                if len(members) != 1:
                    raise BootstrapError(f'Archive must contain exactly one regular {binary} executable.')
                member = members[0]
                if Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                    raise BootstrapError('Unsafe archive member; nothing installed.')
                result[binary] = tar.extractfile(member).read()
    return tag, result


def owned(path, receipt):
    record = receipt.get('files', {}).get(str(path))
    return bool(record and path.is_file() and not path.is_symlink() and sha(path) == record)


def replace_bytes(path, data, mode=0o755):
    fd, temp = tempfile.mkstemp(prefix='.leverage-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def install_bundle(install, receipt_path, receipt, preserve_camp=None):
    targets = []
    for name in ('camp', 'fest', 'festival'):
        path = install / name
        if name == 'camp' and preserve_camp:
            continue
        if path.exists() or path.is_symlink():
            if not owned(path, receipt):
                # Existing compatible components are preserved; no takeover.
                if name == 'fest':
                    continue
                raise BootstrapError(f'Will not replace unmanaged {path}; update through its installer.', 4)
        targets.append(path)
    tag, payload = release_payload()
    if version_tuple(tag) < version_tuple(receipt.get('tag', 'v0.0.0')):
        raise BootstrapError('Will not downgrade a previously installed Festival release.')
    install.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    changed = []
    new_receipt = {'tag': tag, 'files': dict(receipt.get('files', {}))}
    try:
        for path in targets:
            # Recheck ownership immediately before writing.
            if (path.exists() or path.is_symlink()) and not owned(path, receipt):
                raise BootstrapError(f'Install target changed: {path}', 4)
            old[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
            replace_bytes(path, payload[path.name])
            changed.append(path)
            new_receipt['files'][str(path)] = sha(path)
        camp = preserve_camp or install / 'camp'
        if not capable(camp):
            raise BootstrapError('Latest Festival release lacks required leverage flags; no installation retained.', 5)
        replace_bytes(receipt_path, (json.dumps(new_receipt, indent=2) + '\n').encode(), 0o600)
    except BaseException:
        for path in reversed(changed):
            if old[path] is None:
                path.unlink(missing_ok=True)
            else:
                replace_bytes(path, *old[path])
        raise
    say(f'Installed Festival {tag}: {", ".join(p.name for p in changed)} into {install}.')
    return camp


def version_tuple(tag):
    try:
        return tuple(int(n) for n in tag.removeprefix('v').split('-')[0].split('.'))
    except ValueError:
        raise BootstrapError(f'Invalid release version {tag!r}')


def ensure(check=False):
    install = Path(os.environ.get('LEVERAGE_INSTALL_DIR', Path.home() / '.local/bin')).expanduser().absolute()
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'leverage'
    receipt_path = state / 'festival-receipt.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    camp, manager = find_tool('camp', install), find_tool('festival', install)
    if not camp and manager:
        resolved = run([manager, 'resolve', 'camp'])
        candidate = Path(resolved.stdout.strip())
        if resolved.returncode == 0 and candidate.is_absolute() and candidate.is_file():
            camp = candidate
    ready = capable(camp)
    if ready and manager:
        return camp
    if check:
        say('Festival installation/update is needed; --check changed nothing.')
        raise BootstrapError('Run ensure-festival.sh to install/update the required components.', 6)
    if manager:
        # Only let a manager update the binary it owns, never a custom PATH binary.
        resolved = run([manager, 'resolve', 'camp'])
        if camp and resolved.returncode == 0 and Path(resolved.stdout.strip()).resolve() != camp.resolve():
            raise BootstrapError(f'{camp} is not managed by {manager}; update it through its installation channel.', 4)
        result = run([manager, 'update', '--json'])
        if result.returncode:
            raise BootstrapError('Festival update failed: ' + result.stderr.strip())
        info = json.loads(result.stdout)
        # Current managers may wrap update metadata in a data field.
        info = info.get('data', info)
        action = info.get('action')
        if action == 'package':
            raise BootstrapError('Package-managed install needs: ' + info.get('upgrade', 'update with its package manager'), 4)
        if action in ('upgraded', 'current'):
            resolved = run([manager, 'resolve', 'camp'])
            candidate = Path(resolved.stdout.strip())
            if resolved.returncode == 0 and candidate.is_absolute() and capable(candidate):
                say('Festival manager checked/updated its Camp installation.')
                return candidate
            raise BootstrapError('The available Festival release lacks the required leverage capability.', 5)
        if action not in ('absent', 'unmanaged'):
            raise BootstrapError('Unrecognized Festival update result; no fallback installation attempted.')
    if camp and not ready and not owned(camp, receipt):
        raise BootstrapError(f'{camp} is too old and unmanaged. Update through its existing installer.', 4)
    return install_bundle(install, receipt_path, receipt, camp if ready else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='inspect without downloading or changing files')
    args = parser.parse_args()
    try:
        path = ensure(args.check)
        print(path)
        return 0
    except BootstrapError as exc:
        say(str(exc))
        return exc.code
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.SubprocessError) as exc:
        say(str(exc))
        return 3
    except KeyboardInterrupt:
        say('Canceled.')
        return 130


if __name__ == '__main__':
    sys.exit(main())
