# crush: measured snapshot

[Read the report](report.md) · [SVG](assets/contributors.svg) · [CSV](data/contributors.csv) · [Provenance](source.json)

Source: [charmbracelet/crush](https://github.com/charmbracelet/crush/tree/77bfd1a708e19b58d3c6525c46dd0c2c3add3cf7)

Revision: `77bfd1a708e19b58d3c6525c46dd0c2c3add3cf7`. Source commit date: 2026-01-24T19:42:55-03:00. Measurement generated: 2026-11-09T05:39:13.476706Z.

Status: **complete**. Dirty: `False`. Shallow: `False`. Contributor export threshold: **0%**.

The measurement date is not the source commit date. This is a pinned checkout snapshot, not a claim about the latest upstream code.

## Scope and reproduction

The exact scan arguments, configuration hashes, tool versions, history method and scope fingerprints are in `source.json`. Repository-relative configuration paths refer to files at the source revision. No additional generated/imported-code audit was performed.

The exact local ref names and commit IDs are preserved in [refs.txt](refs.txt); the archive verifies that they match the measured `refs_digest`. Recreate those refs in a separate full-history clone when attempting an exact historical rerun.

Use a full-history checkout at the recorded revision, matching configuration and tool versions, then run from the leverage repository:

```sh
python3 skills/leverage/scripts/collect.py /path/to/source --output /path/outside/source/new-report --png
```

Camp uses all local Git refs for commit spans. Matching HEAD alone does not recreate the historical denominator: compare `refs_digest`, the other fingerprints and exact metrics before treating a new run as the same measurement. Fresh clones and later fetches can change those inputs.

Original raw exports stay outside this archive because they include email identities and local paths. Their SHA-256 hashes identify the inputs; the portable snapshot and full CSV retain exact numeric values and display names. Hashes identify files, not independent proof of their authenticity.

Calendar-span estimates do not measure actual hours or establish AI use. Contributor ratios must not be summed to reproduce the repository score.
