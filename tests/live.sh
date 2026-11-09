#!/usr/bin/env bash
# Only executed inside the disposable test container.
set -euo pipefail
[ "${LEVERAGE_TEST_ISOLATED:-}" = 1 ] || exit 2
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp -R /src/skills/leverage "$work/installed-skill"
skill="$work/installed-skill"
# No camp/fest/festival is preinstalled in this image. Install the real release.
camp_path="$(bash "$skill/scripts/ensure-festival.sh")"
"$camp_path" version
"$HOME/.local/bin/festival" version
"$HOME/.local/bin/fest" version
mkdir "$work/repo"
cd "$work/repo"
git init -q
git config user.name Alice
git config user.email alice@example.test
printf 'package main\n\nfunc main() { println("hello") }\n' > main.go
git add main.go
git commit -qm initial
mkdir .repos
printf 'package vendor\n' > .repos/vendor.go
git add .repos
git -c user.name=Vendor -c user.email=vendor@example.test commit -qm vendor
printf '.repos/\n' > .sccignore
printf 'package main\nconst Added = 42\n' > added.go
git status --porcelain > "$work/before"
python3 "$skill/scripts/collect.py" "$work/repo" --output "$work/report" --png
python3 "$skill/scripts/collect.py" "$work/repo" --output "$work/personal" --mode personal --author alice@example.test
python3 "$skill/scripts/collect.py" "$work/repo" --output "$work/summary" --mode summary --people 2
python3 "$skill/scripts/render.py" --repository "$work/report/raw/repository.json" --contributors "$work/report/raw/contributors.json" --output "$work/light" --theme light --png
python3 - "$work" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
a=json.loads((root/'report/data/snapshot.json').read_text())
b=json.loads((root/'personal/data/snapshot.json').read_text())
assert a['status']=='complete'
assert len(a['contributors'])==1
assert a['contributors'][0]['name']=='Alice'
assert a['contributors'][0]['leverage']==b['score']['full_leverage']
assert a['summary']['files']==2
assert a['summary']['buckets']['uncommitted']['lines']>0
assert (root/'report/assets/contributors.png').read_bytes().startswith(b'\x89PNG')
print('PASS: real Festival install, copied skill, unregistered repo, all views, ignore rules, dirty source, exact personal parity, PNG and offline rerender')
PY
git status --porcelain > "$work/after"
cmp "$work/before" "$work/after"
test ! -e .campaign
