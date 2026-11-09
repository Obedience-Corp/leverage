"""Render saved Camp JSON into Markdown, portable data and exact SVG charts."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from report_data import BUCKETS, normalize, require

LABELS = {'contributors': 'Eligible contributors', 'excluded_identities': 'Excluded identities',
          'uncommitted': 'Uncommitted', 'unavailable': 'Unavailable'}


def fmt(value, digits=2, suffix=''):
    return 'unavailable' if value is None else f'{value:,.{digits}f}{suffix}'


def mdtext(value):
    return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')


def ordered(data, sort):
    if sort == 'ratio':
        return sorted(data['contributors'], key=lambda r: (r['leverage'] is None, -(r['leverage'] or 0), r['row_id']))
    return sorted(data['contributors'], key=lambda r: (-r['lines'], r['row_id']))


def figure(data, theme, sort, top):
    rows = ordered(data, sort)[:min(top, 8)]
    height = 650 + 50 * max(1, len(rows))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">' + html.escape(data['repository'] + ' leverage report: ' + data['status']) + '</title>',
             '<desc id="desc">' + html.escape(f"Sorted by {sort}. Bars encode physical-line share, not model ratio. {len(data['contributors'])} rows collected; null ratios are unavailable. Status {data['status']}.") + '</desc>',
             f'<rect width="1200" height="{height}" rx="24" fill="{theme["background"]}"/>']

    def text(x, y, value, size=18, color='text', anchor='start'):
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{size}" fill="{theme[color]}" text-anchor="{anchor}">{html.escape(str(value))}</text>')

    def rect(x, y, w, h, color, radius=0):
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(0,w):.2f}" height="{h}" rx="{radius}" fill="{theme[color]}"/>')

    text(52, 48, 'CAMP / REPOSITORY LEVERAGE', 14, 'primary')
    title = data['repository']
    text(52, 100, title[:46] + ('…' if len(title) > 46 else ''), 34)
    text(1148, 48, data['generated_at'][:10], 14, 'muted', 'end')
    text(1148, 78, (data['revision'] or 'unborn')[:12], 14, 'muted', 'end')
    text(52, 137, f"{data['status'].upper()} · {data['view']} view · calendar-span effort proxy", 18, 'muted')
    summary = data['summary']
    cards = [(f"{summary['code_lines']:,}", 'COUNTED CODE LINES'),
             (str(len(data['contributors'])) if data['contributors_collected'] else 'not collected', 'CONTRIBUTOR ROWS'),
             (fmt(summary['estimated_person_months'], 1), 'ESTIMATED PERSON-MONTHS')]
    for x, (value, label) in zip((52, 425, 798), cards):
        rect(x, 173, 350, 112, 'panel', 14)
        text(x + 24, 219, value, 30)
        text(x + 24, 257, label, 12, 'muted')
    text(52, 329, f"Contributors sorted by {'line ownership' if sort == 'ownership' else 'model ratio'}", 24)
    text(52, 357, 'Bar length is share of all counted physical lines. Ratios are a separate metric.', 16, 'muted')
    text(52, 397, 'CONTRIBUTOR', 12, 'muted')
    text(940, 397, 'SHARE', 12, 'muted', 'end')
    text(1148, 397, 'MODEL RATIO', 12, 'muted', 'end')
    maximum = max((r['share'] for r in rows), default=0)
    axis = min(1, max(.1, math.ceil(maximum * 10) / 10))
    bottom = 430 + 50 * max(1, len(rows))
    for tick in range(5):
        x = 304 + tick * 540 / 4
        rect(x, 414, 1, bottom - 414, 'grid')
        text(x, bottom + 22, f'{axis * tick / 4:.1%}', 12, 'muted', 'middle')
    if not rows:
        text(52, 448, 'No contributor rows collected' if not data['contributors_collected'] else 'No surviving attributable lines', 18, 'muted')
        if data['score']:
            text(52, 475, 'Selected score: ' + fmt(data['score']['full_leverage'], suffix='x'), 18)
    for i, row in enumerate(rows):
        y = 445 + 50 * i
        name = row['name']
        text(52, y + 3, name[:24] + ('…' if len(name) > 24 else ''), 17)
        rect(304, y - 17, 540 * row['share'] / axis, 26, 'primary' if i == 0 else 'secondary', 4)
        text(940, y + 3, fmt(row['share'] * 100, suffix='%'), 17, anchor='end')
        text(1148, y + 3, fmt(row['leverage'], suffix='x'), 17, anchor='end')
    panel = bottom + 58
    rect(52, panel, 1096, 106, 'panel', 14)
    text(76, panel + 29, 'LINE ACCOUNTING', 12, 'muted')
    x = 76
    colors = ['primary', 'excluded', 'uncommitted', 'unavailable']
    for key, color in zip(BUCKETS, colors):
        bucket = summary['buckets'][key]
        width = 1048 * bucket['share']
        rect(x, panel + 42, width, 14, color)
        x += width
    for i, (key, color) in enumerate(zip(BUCKETS, colors)):
        text(76 + i * 270, panel + 84, f"{LABELS[key]} {summary['buckets'][key]['share']:.2%}", 13, color)
    text(52, height - 25, 'Estimated effort / calendar span. Not hours worked or proof of AI use. See report.md for scope and diagnostics.', 14, 'muted')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def markdown(data, sort, top):
    s = data['summary']
    lines = [f"# {mdtext(data['repository'])}: Camp leverage report", '',
             f"**Status:** {data['status']} · **Snapshot:** {mdtext(data['generated_at'])} · **Revision:** `{mdtext(data['revision'] or 'unborn')}`", '',
             '![Repository leverage and contributor ownership](assets/contributors.svg)', '',
             '| Measurement | Result |', '| :--- | ---: |',
             f"| Files | {s['files']:,} |", f"| Code lines | {s['code_lines']:,} |",
             f"| Physical lines | {s['lines']:,} |", f"| Estimated effort (PM) | {fmt(s['estimated_person_months'])} |"]
    if data['score']:
        lines += [f"| {'Personal' if data['view']=='personal' else 'Repository'} ratio | {fmt(data['score']['full_leverage'], suffix='x')} |",
                  f"| Effort basis | {mdtext(data['effort_method'])} |"]
    if data['matched_identities'] is not None:
        lines += [f"| Matched author identities | {data['matched_identities']} |"]
    lines += ['', '## Contributors', '', f"Sort: {sort}. Showing up to {top} of {len(data['contributors'])} collected rows.", '',
              '| Contributor | Physical lines | Share | Est. PM | Span PM | Ratio |',
              '| :--- | ---: | ---: | ---: | ---: | ---: |']
    for row in ordered(data, sort)[:top]:
        lines.append(f"| {mdtext(row['name'])} | {row['lines']:,} | {row['share']:.2%} | {fmt(row['estimated_person_months'])} | {fmt(row['elapsed_person_months'])} | {fmt(row['leverage'], suffix='x')} |")
    if not data['contributors_collected']:
        lines += ['', 'Contributor data was not collected for this view.']
    elif not data['contributors_complete']:
        lines += ['', f"Input was filtered: {data['omitted_contributors']} contributor rows were omitted by Camp. CSV contains the collected rows only."]
    lines += ['', '[Contributor CSV](data/contributors.csv) · [Snapshot metadata](data/snapshot.json)', '',
              '## Line accounting', '', '| Bucket | Physical lines | Share | Estimated PM |', '| :--- | ---: | ---: | ---: |']
    for key in BUCKETS:
        b = s['buckets'][key]
        lines.append(f"| {LABELS[key]} | {b['lines']:,} | {b['share']:.2%} | {fmt(b['estimated_person_months'])} |")
    lines += ['', '## Method and diagnostics', '',
              'PM means person-months. COCOMO effort is allocated by surviving physical-line ownership. Contributor ratios divide that allocation by repository-wide local-ref commit spans, floored at 0.1 months. Exclusions limit current source ownership, not the historical span. Repository summary and manual team-size views have their own recorded effort basis; contributor ratios must not be added.', '',
              'Calendar span is not a timesheet. A result covers one repository, not a person’s total work or proof of AI use. Uncommitted, excluded and unavailable shares are kept separate. Null ratios are unavailable, not zero.', '',
              'Diagnostic codes: ' + (', '.join(data['diagnostic_codes']) or 'none') + '.', '',
              'Raw exports, when present under `raw/`, include original identities and local paths. Portable data omits email IDs and local paths; display names are retained. Nothing was published.']
    return '\n'.join(lines) + '\n'


def write_bundle(data, output, top=10, sort='ownership', theme='dark', png=False):
    require(1 <= top <= 1000, 'top must be from 1 to 1000')
    output = Path(output)
    (output / 'assets').mkdir(parents=True, exist_ok=True)
    (output / 'data').mkdir(exist_ok=True)
    themes = json.loads((Path(__file__).resolve().parent.parent / 'assets/theme.json').read_text())
    require(theme in themes, 'Unknown theme')
    svg = output / 'assets/contributors.svg'
    svg.write_text(figure(data, themes[theme], sort, top))
    (output / 'report.md').write_text(markdown(data, sort, top))
    (output / 'data/snapshot.json').write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    fields = ['row_id', 'name', 'lines', 'share', 'estimated_person_months', 'elapsed_person_months', 'leverage', 'history_complete']
    with (output / 'data/contributors.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in ordered(data, sort):
            copy = dict(row)
            if copy['name'].startswith(('=', '+', '-', '@')):
                copy['name'] = "'" + copy['name']  # spreadsheet formula protection
            writer.writerow(copy)
    if png:
        tool = shutil.which('rsvg-convert')
        if tool:
            subprocess.run([tool, '-o', str(output / 'assets/contributors.png'), str(svg)], check=True, timeout=60)
        else:
            print('leverage: SVG/report saved; optional PNG omitted (install rsvg-convert).', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'contributors', 'personal'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--sort', choices=('ownership', 'ratio'), default='ownership')
    parser.add_argument('--theme', choices=('dark', 'light'), default='dark')
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args()
    try:
        data = normalize(**{key: json.loads(getattr(args, key).read_text()) if getattr(args, key) else None
                            for key in ('repository', 'contributors', 'personal')})
        require(not args.output.exists() or not any(args.output.iterdir()), 'Use a new or empty render output directory')
        # Do not render into any supplied report's source Git tree.
        for key in ('repository', 'contributors', 'personal'):
            path = getattr(args, key)
            if path:
                from report_data import scope_of
                source = scope_of(json.loads(path.read_text()))
                root = Path(source['git_root']).resolve()
                require(not args.output.resolve().is_relative_to(root), 'Output must be outside the analyzed Git root')
        write_bundle(data, args.output, args.top, args.sort, args.theme, args.png)
        print(args.output / 'report.md')
        return 2 if data['status'] == 'partial' else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('leverage: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
