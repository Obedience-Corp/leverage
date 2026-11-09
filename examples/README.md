# Synthetic example

For measurements of public AI projects, browse the [real repository reports](../reports/README.md).

These two small synthetic Camp-shaped inputs demonstrate accounting and rendering, not measurements of a real repository. 1,000 physical lines receive 10 estimated PM: Alice owns 800 lines (8 PM / 2 span PM = 4x), Bob owns 100 (1 PM / 0.1 span PM = 10x), and 100 are uncommitted (1 PM without an individual ratio).

The repository summary ratio uses its own supplied fixture denominator. No contributor ratios are summed. Source date is June 15, 2025 deliberately: rerendering must preserve the source timestamp instead of replacing it with today's date.

View [the report](report/report.md) or [the standalone SVG](report/assets/contributors.svg). Rebuild into a new directory:

```sh
python3 skills/leverage/scripts/render.py --repository examples/repository.json \
  --contributors examples/contributors.json --output /path/to/new-example --png
```
