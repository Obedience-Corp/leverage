---
name: leverage
description: Calculate Camp leverage scores for a Git repository or author and generate contributor tables, CSV, SVG charts and optional PNGs. Use for repository leverage reports or rendering saved Camp JSON into visual reports.
---

# Leverage

Use Camp's scoring; the bundled scripts collect and render its output. No camp or festival workspace is required. `<skill-dir>` is the directory containing this file; resolve it from the installed skill location, not cwd.

## Fresh report

Use the requested local Git checkout, otherwise the current checkout. Run:

```sh
python3 "<skill-dir>/scripts/collect.py" /path/to/repo --png
```

The default collects a repository summary and full contributor breakdown, then writes Markdown, SVG, CSV, portable metadata and raw exports to a new sibling directory of the Git root. Report the output path. Optional PNG needs `rsvg-convert`; SVG and the report still work without it. A chosen `--output` must be outside the source Git root.

Select `--mode summary` for only repository scoring, or `--mode personal --author EMAIL` for an author selection. `--people N` overrides summary team size. `--top N`, `--sort ownership|ratio` and `--theme dark|light` control presentation; raw rows remain complete. Prefer ownership order unless the user asks otherwise. Personal selectors can match several identities; report that count.

Collection bootstraps Festival when needed via `scripts/ensure-festival.sh`. Show its stderr install/update notices to the user. It verifies checksums, preserves unmanaged tools, returns the verified Camp path and does not create a camp or link the repo. Use [installation.md](references/installation.md) for missing dependencies or ownership/platform failures. To inspect without installing, run `bash "<skill-dir>/scripts/ensure-festival.sh" --check`. An explicitly supplied `--camp /absolute/path` skips bootstrap after a capability check.

Git, Python 3.11+ and scc are required; provide the relevant missing-tool instruction or perform an already-authorized install. Do not install another Python distribution as a side effect. No API key or image-generation model is needed.

## Saved reports / new styling

Render matching saved exports without installing Festival or rescanning:

```sh
python3 "<skill-dir>/scripts/render.py" \
  --repository /path/to/summary.json --contributors /path/to/contributors.json \
  --output /path/to/new-bundle --png
```

Use `--personal` for a saved personal report. A new theme/top-N uses saved data. Supplied snapshots must match; do not join incompatible runs. See [output-contracts.md](references/output-contracts.md) for schema and partial/empty data behavior.

## Interpret and deliver

Inspect the SVG/PNG at reading size, check the table against the source values, and give the user links to `report.md`, the chart and CSV. Exit 2 means a partial report was written: state its diagnostics and unavailable ratios. Exit 1 is a failure, never a zero-productivity result. Raw captures contain original identities/paths; portable data keeps display names but omits emails/local paths. CSV spreadsheet-formula prefixes are escaped.

Use [measurement.md](references/measurement.md) when explaining scores. Ratios are estimated effort divided by calendar-span proxies; they do not measure actual hours or prove AI use. One repo does not represent a person's total work. Excluded, uncommitted and unavailable allocations stay separate, and contributor ratios are never summed.

Do not edit ignore rules, commit, fetch other repos, or upload/publish artifacts unless the user requests it. Use a new output directory to avoid overwriting unrelated files or including generated output in the source scan.
