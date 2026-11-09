# Data and artifact contracts

Accepted input schemas: `leverage-repository/v1` for repository/personal views and `leverage-contributors/v1` with method `contributor_worktree_v1` for contributor exports. This version handles one selected Git repository, not a camp-wide multi-project export. Combined snapshots must match target, root, HEAD, manifest/content/identity/ref fingerprints, file/line/estimate counts, configuration, scan arguments and tools. A mismatch is an error, not an invitation to blend runs.

Normalize every supplied report before writing presentation. Reject non-finite/negative numeric data, unknown status, duplicate identities, broken accounting and invalid shares. Collection gets full contributor output using `--author-threshold 0`; supplied filtered data is allowed only with visible omitted counts. CSV contains collected rows, not an invented complete roster. Presentation top-N and ordering never change allocations.

Exit 0 is complete or empty. Exit 2 means a valid partial bundle was produced. Missing history/attribution is shown as unavailable, with diagnostic codes; null does not become zero. A fatal collection, schema or render failure exits 1, preserving completed raw captures when possible. Ctrl+C cancels Camp's process group on macOS/Linux; partial captures remain for diagnosis, not as a finished report.

Bundle: `report.md`, `assets/contributors.svg`, optional `assets/contributors.png`, `data/contributors.csv`, `data/snapshot.json`. Collection additionally writes original JSON exports, per-command stderr, `raw/diagnostics.txt` and `raw/collection.json`. Render-only mode writes no raw files and performs no scan/bootstrap.

Portable schema `leverage-skill/v1` keeps display names, source times/revision, tool versions, fingerprints, accounting, selected score and effort method, nullable row metrics, omitted counts and diagnostic codes. Local paths/email IDs are omitted; row IDs are stable truncated hashes of original IDs, not a guarantee of anonymity. Raw exports still contain original identities/paths. CSV escapes leading spreadsheet formula markers in names; numeric fields retain source precision.

Use a new output directory outside the source Git root. Existing render inputs can be reused for a new theme/top-N without rescoring. SVG bars encode line share on a zero-based linear axis; ratios are separately labeled. Default ordering is ownership. PNG converts the SVG using rsvg-convert and never invents or estimates chart data.
