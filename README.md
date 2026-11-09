<h1 align="center">Festival Leverage Score</h1>

<p align="center">Turn your Git history into a report you can share.</p>

<p align="center">
  <a href="https://github.com/Obedience-Corp/festival"><img src="https://img.shields.io/badge/built%20with-Festival-7c3aed.svg" alt="Built with Festival"></a>
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="#read-the-score">Read the score</a> ·
  <a href="examples/README.md">Explore the example</a>
</p>

Turn a local Git repository into a Festival Leverage Score report: an estimated effort ratio, contributor breakdown, and charts you can share. Ask your coding agent to run it, then open the report.

[Festival](https://github.com/Obedience-Corp/festival) provides the tools behind the score. Its Camp CLI runs the calculation through `camp leverage`, and this skill turns the output into a report. You can use it on an existing repository without setting up a camp workspace or a Festival plan.

![Example contributor report with ownership shares and effort ratios](examples/report/assets/contributors.svg)

*Example data, not a real team's results. [See the report and its inputs.](examples/README.md)*

## Get started

This repository is currently a private preview; installation requires GitHub access.

Ask your agent's skill installer:

```text
Install the leverage skill from https://github.com/Obedience-Corp/leverage/tree/main/skills/leverage
```

Then, from the repository you want to measure:

```text
Use leverage to calculate this repo's Festival Leverage Score
and generate a visual contributor report.
```

You'll get a Markdown report, an SVG chart, a contributor CSV, snapshot metadata, and the original JSON exports. PNG is available when `rsvg-convert` is installed. Reports go into a new directory beside your repository. The skill leaves your source files alone and keeps the results local.

You can also ask for a personal view or a different presentation:

> Calculate my Festival Leverage Score for this repo using alice@example.com.

> Render my saved report with the light theme.

<details>
<summary>Install manually in Codex or Claude Code</summary>

Clone the repository and copy the skill into your client's skill directory:

```sh
git clone git@github.com:Obedience-Corp/leverage.git
mkdir -p ~/.codex/skills
if [ ! -e ~/.codex/skills/leverage ]; then
  cp -R leverage/skills/leverage ~/.codex/skills/leverage
fi
```

For Claude Code, use `~/.claude/skills` in place of `~/.codex/skills`. The copy above preserves an existing installation. To update, replace it with a reviewed revision. The skill directory contains everything needed at runtime; you can remove the source checkout afterward. Reload your client's skill discovery if needed.

</details>

## Read the score

The Festival Leverage Score compares an estimate of the effort represented by the current code with an effort proxy based on Git history. It uses [scc](https://github.com/boyter/scc)'s COCOMO model for the estimate and calendar spans for the proxy. Repository and personal views record the effort basis they use.

For contributors, estimated effort is allocated by their share of surviving physical lines, including comments and blanks. That allocation is divided by the repository-wide commit span, with a minimum of 0.1 months. A contributor with 8 estimated person-months of code and a 2-month span has a **4× ratio**.

Read that as a model-based estimate. Git history cannot tell you how many hours someone worked, how good the software is, or whether they used AI. Short histories, imported code, and squash merges can affect the result. One repository only covers part of a person's work.

The chart's bars show code ownership. Ratios are listed separately, and contributor ratios should never be added to get a repository score. [Read the measurement details.](skills/leverage/references/measurement.md)

## Keep the evidence with the chart

Each report includes the data behind it:

| File | What it contains |
| --- | --- |
| `report.md` | Score, contributor table, method, and diagnostics |
| `assets/contributors.svg` | Chart for a README, post, or presentation |
| `data/contributors.csv` | Full contributor table for further analysis |
| `data/snapshot.json` | Portable metadata and exact metrics |
| `raw/` | Original exports and collection diagnostics |

Check the report's scope and diagnostics before sharing a result. Raw exports contain original identities and local paths. Portable data omits emails and local paths but retains display names. Publishing is up to you.

## Requirements

You'll need Python 3.11+, Git, and scc. The skill installs missing Festival components when needed, verifies official release checksums, and reuses compatible installations. It preserves custom binaries and reports installs and updates.

Automatic setup supports macOS and Linux; use WSL2 on Windows. PNG export also needs `rsvg-convert`. No API key or paid service is required to calculate or render a report.

[Installation and troubleshooting](skills/leverage/references/installation.md) · [Output formats and partial reports](skills/leverage/references/output-contracts.md)

<details>
<summary>Run the scripts directly</summary>

| Request | Mode | What it collects |
| :--- | :--- | :--- |
| Repository score and contributor chart | `overview` (default) | Summary and all attributable contributor rows |
| Repository score only | `summary` | Summary; no contributor rows |
| One author's score | `personal --author EMAIL` | Selected score and matched-identity count; no contributor rows |

Personal and summary images show the selected ratio and effort proxy. Source counts, estimated repository effort and line accounting still describe the whole repository; their CSV is header-only. Personal selectors can match several identities, so inspect the matched count before comparing with one contributor row. Contributor rows represent surviving line owners, not everyone who ever committed.

```sh
# Repository report with an optional PNG
python3 skills/leverage/scripts/collect.py /path/to/repo --png

# Personal view
python3 skills/leverage/scripts/collect.py /path/to/repo \
  --mode personal --author alice@example.com

# Summary with an explicit team size
python3 skills/leverage/scripts/collect.py /path/to/repo --mode summary --people 2

# Restyle saved exports without rescanning
python3 skills/leverage/scripts/render.py \
  --repository /path/to/summary.json --contributors /path/to/contributors.json \
  --output /path/to/new-report --theme light --sort ratio --png
```

Use `--output` to choose a new directory outside the source repository. Exit code 2 means a partial report was written; its diagnostics explain what's missing. Use `--camp /absolute/path` to supply an existing Camp executable and skip automatic setup after capability verification.

After a default run, the saved inputs are `<report>/raw/repository.json` and `<report>/raw/contributors.json`. Pass those to `render.py` for another theme or sort order; it does not invoke Camp, Git, scc or the installer. Omit `--png` to render without any external commands. The table shows up to `--top` rows (10 by default), the SVG shows up to eight, and the CSV retains every collected row. Sorting by ratio keeps bar lengths tied to physical-line share.

To rerender a personal report, use `--personal <report>/raw/personal.json`. For a summary-only report, use `--repository <report>/raw/repository.json` without `--contributors`. Use inputs from the same snapshot when combining files.

To check dependencies without network requests or writes:

```sh
bash skills/leverage/scripts/ensure-festival.sh --check
```

</details>

## Development

```sh
just test all   # deterministic tests in a disposable container
just test live  # verified Festival install and a repo outside a camp
```

Tests run against a copy of the installable skill as an unprivileged container user. Runtime Python uses the standard library; PyYAML is a test dependency. The test image includes scc and a PNG rasterizer. All bundled examples use synthetic data.
