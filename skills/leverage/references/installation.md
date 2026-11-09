# Installation and readiness

Run `bash <skill-dir>/scripts/ensure-festival.sh`. Exit 0 prints exactly the absolute capable Camp path; stderr carries install/update notices. Use that path for scoring. `--check` makes no network calls or writes. Statuses: 3 bootstrap failed, 4 installation-owner action required, 5 feature not in the available release, 6 check-only action needed. Never score with a non-ready result.

The helper supports macOS (Intel/ARM) and Linux (x86_64/ARM64), using official `Obedience-Corp/festival` release archives and SHA-256 checksums. The archive must contain `camp`, `fest`, and `festival`. It installs into `~/.local/bin`, or the explicit `LEVERAGE_INSTALL_DIR`, with a receipt under `${XDG_STATE_HOME:-~/.local/state}/leverage`. It never edits shell profiles, initializes a camp or links a repository. The returned path works even if its directory is not on PATH.

Compatible Camp plus a Festival manager is reused without an update check. Missing Festival components are installed from the verified bundle. A compatible custom Camp is preserved and returned; the helper can install the missing manager/Fest without taking over that custom Camp. Owned files are recognized by path AND checksum. An old unmanaged Camp requires an update through its original installer. A manager-owned older Camp is updated with `festival update --json`; package-managed installations return the appropriate owner update action. No forced update, downgrade, unverified archive or silent takeover is allowed. Hooks do not run installation at unrelated session starts.

Python 3.11+ and Git are required. scc is separate from Festival: on macOS an available Homebrew can install it with `brew install scc`; otherwise consult the official [scc releases](https://github.com/boyter/scc/releases). Carry out an already-authorized tool installation or explain the missing dependency. Do not install a Python distribution implicitly.

PNG is optional. With `rsvg-convert` available, `--png` rasterizes the exact SVG. SVG, data and Markdown still work when the rasterizer is absent. Install a rasterizer only within the user's authorized scope.

Automatic native Windows bootstrap is not claimed. Use this skill inside WSL2, or install Festival through its documented native Windows/Scoop route, then use an explicit verified `--camp` executable for Python collection. Native Windows collection requires Python/Git/scc and has not been runtime-verified in this release. See [Festival installation](https://github.com/Obedience-Corp/festival#readme).
