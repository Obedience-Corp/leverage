# leverage

Runtime skill is `skills/leverage/`, self-contained after copy/install. Camp owns scoring; this repo owns dependency readiness, collection and rendering. Preserve original raw exports and exact metrics; display rounding belongs only in presentation.

Use `just test all` for deterministic tests, `just test live` for real bootstrap + outside-camp proof. Filesystem/install/Git fixture mutations run inside containers, not on the host. Inspect generated SVG/PNG at reading size before claiming visual completion. Runtime Python uses only the standard library; PNG uses optional rsvg-convert.

Keep the repo private unless explicitly instructed to change visibility. Use camp project commit wrappers, include DCO sign-off, and open ready-for-review PRs. Do not add agent coauthor trailers. Documentation should describe the calendar-span estimate accurately and never treat it as measured hours or proof of AI use.

`reports/` holds real, dated repository snapshots outside the installable skill. Use `scripts/archive_report.py` with matching full exports and run `just reports check`. Keep original raw captures out of git; preserve numeric data, source/config/ref provenance and any explicit scope override. Add a new directory for a new measurement rather than replacing an old one.
