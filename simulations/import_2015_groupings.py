#!/usr/bin/env python3
"""Extract the riding groupings used by the original 2015 simulations.

The 2015 results on the site were supplied by outside contributors. Their
spreadsheets (kept in https://github.com/smcmurtry/electoral_reform) record how
the 338 ridings of the 2013 representation order were grouped:

  data/mmp/2015AMMP12.3.xlsx  Wilf Day's Mixed Member Proportional model:
      ridings grouped into regions, each with a number of local and regional MPs.
  data/dmp/DMP_2015_Federal_Election_Votes.xlsx  Rhys Goldstein's Dual Member
      Proportional model: ridings merged (mostly in pairs) into two-seat districts.

This script turns those into plain CSVs in simulations/data/groupings/ so the
same groupings can be reused for the 2019 and 2021 elections, which were fought
on the same boundaries.

Usage:
  python3 simulations/import_2015_groupings.py path/to/electoral_reform

Output:
  mmp_regions_2013.csv    riding_number, region
  mmp_region_seats_2013.csv  region, prov, local_seats, regional_seats, plus the
                          local seats by party that Wilf Day assumed (for validation)
  dmp_districts_2013.csv  riding_number, district, prov

Standard library only.
"""
import collections
import csv
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import results  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'groupings')
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def read_xlsx(path):
    """Rows of the first worksheet, as lists of strings."""
    z = zipfile.ZipFile(path)
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
            strings.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheet = ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', NS)[0]
    target = rels[sheet.get('{%s}id' % NS['r'])]
    root = ET.fromstring(z.read(target.lstrip('/') if target.startswith('/') else 'xl/' + target))
    rows = []
    for row in root.iter('{%s}row' % NS['m']):
        cells = {}
        for c in row.findall('m:c', NS):
            letters = re.match(r'[A-Z]+', c.get('r')).group(0)
            col = 0
            for ch in letters:
                col = col * 26 + ord(ch) - 64
            v = c.find('m:v', NS)
            if c.get('t') == 's' and v is not None:
                cells[col - 1] = strings[int(v.text)]
            elif v is not None:
                cells[col - 1] = v.text
        out = [''] * (max(cells) + 1 if cells else 0)
        for k, v in cells.items():
            out[k] = v
        rows.append(out)
    return rows


def num(row, i):
    try:
        return int(round(float(row[i])))
    except (IndexError, ValueError):
        return 0


PROV_OF_REGION_PREFIX = [
    ('Newfoundland', 'NL'), ('Prince Edward', 'PE'), ('Nova Scotia', 'NS'), ('New Brunswick', 'NB'),
    ('Saskatchewan', 'SK'), ('Yukon', 'YT'), ('Northwest', 'NT'), ('Nunavut', 'NU'),
]


def import_mmp(xlsx, ridings):
    rows = read_xlsx(xlsx)
    # 2015 ridings keyed by their (Conservative, Liberal, NDP) votes, which is unique.
    key = {}
    for r in ridings.values():
        key[(r.votes['Conservative'], r.votes['Liberal'], r.votes['NDP'])] = r.number

    header = re.compile(r'\(\s*(\d+)\s*\+\s*(\d+)\s*\)')
    items = []  # ('riding', number) or ('region', name, local, regional, row)
    for row in rows:
        if not row or not row[0].strip():
            continue
        k = (num(row, 2), num(row, 4), num(row, 5))
        m = header.search(row[0])
        if row[0].strip().startswith(('Yukon', 'Northwest Territories', 'Nunavut')) and k in key:
            # Territories: one riding each, which is also its own region. The
            # version of the model used on the site gives each an extra regional seat.
            name = row[0].strip()
            items.append(('break',))
            items.append(('riding', key[k]))
            items.append(('region', name, 1, 1, row))
        elif k in key and not m:
            items.append(('riding', key[k]))
        elif m and 'regions' in row[0]:
            items.append(('break',))  # province heading: ends the previous block
        elif m and 'regions' not in row[0] and not row[0].startswith('Canada'):
            name = row[0][:m.start()].strip()
            name = re.sub(r'\s*\d+\s*$', '', name).strip(' :')
            items.append(('region', name, int(m.group(1)), int(m.group(2)), row))

    # A region header sits either directly above or directly below its ridings.
    # Decide which by checking the header's total votes against the block.
    blocks = []
    current = []
    for it in items:
        if it[0] == 'riding':
            current.append(it[1])
        elif it[0] == 'break':
            blocks.append(current)
            current = []
        else:
            blocks.append(current)
            blocks.append(it)
            current = []
    blocks.append(current)
    region_of = {}
    seats = []
    used = set()
    for i, b in enumerate(blocks):
        if isinstance(b, tuple):
            # Compare on Conservative + Liberal + NDP votes (the sheet's own
            # totals leave out some minor candidates).
            target = num(b[4], 2) + num(b[4], 4) + num(b[4], 5)
            for j in (i - 1, i + 1):
                block = blocks[j] if 0 <= j < len(blocks) and isinstance(blocks[j], list) else []
                if j in used or not block:
                    continue
                block_votes = sum(ridings[n].votes[p] for n in block for p in ('Conservative', 'Liberal', 'NDP'))
                if abs(block_votes - target) <= 0.002 * target:
                    used.add(j)
                    for n in block:
                        region_of[n] = b[1]
                    prov = ridings[block[0]].prov
                    local = {'Bloc': num(b[4], 81), 'Conservative': num(b[4], 82), 'Green': num(b[4], 83),
                             'Liberal': num(b[4], 84), 'NDP': num(b[4], 85)}
                    seats.append([b[1], prov, b[2], b[3]] + [local[p] for p in results.PARTIES[:5]])
                    break
            else:
                raise SystemExit('Could not place region %r' % b[1])
    missing = [n for n in ridings if n not in region_of]
    if missing:
        raise SystemExit('Ridings without an MMP region: %s' % missing)

    with open(os.path.join(OUT, 'mmp_regions_2013.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['riding_number', 'riding_name', 'region'])
        for n in sorted(region_of):
            w.writerow([n, ridings[n].name, region_of[n]])
    with open(os.path.join(OUT, 'mmp_region_seats_2013.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['region', 'prov', 'local_seats', 'regional_seats'] +
                   ['assumed_local_' + p for p in results.PARTIES[:5]])
        w.writerows(seats)
    sizes = collections.Counter(region_of.values())
    bad = [(s[0], sizes[s[0]], s[2] + s[3]) for s in seats
           if sizes[s[0]] != s[2] + s[3] and s[1] not in results.TERRITORIES]
    print('MMP: %d regions, %d ridings, %d seats; size mismatches: %s'
          % (len(seats), len(region_of), sum(s[2] + s[3] for s in seats), bad))


def import_dmp(xlsx, ridings):
    rows = read_xlsx(xlsx)
    head = rows[0]
    i_num, i_riding = head.index('District Number'), head.index('Riding')
    district_of = {}
    for row in rows[1:]:
        if row and row[i_num].strip():
            district_of[int(float(row[i_num]))] = row[i_riding].strip()
    missing = [n for n in ridings if n not in district_of]
    if missing:
        raise SystemExit('Ridings without a DMP district: %s' % missing)
    with open(os.path.join(OUT, 'dmp_districts_2013.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['riding_number', 'riding_name', 'district', 'prov'])
        for n in sorted(district_of):
            w.writerow([n, ridings[n].name, district_of[n], ridings[n].prov])
    sizes = collections.Counter(collections.Counter(
        (ridings[n].prov, d) for n, d in district_of.items()).values())
    print('DMP: %d districts; ridings per district: %s' % (sum(sizes.values()), dict(sizes)))


def main(repo):
    os.makedirs(OUT, exist_ok=True)
    ridings = results.load(2015)
    import_mmp(os.path.join(repo, 'data', 'mmp', '2015AMMP12.3.xlsx'), ridings)
    import_dmp(os.path.join(repo, 'data', 'dmp', 'DMP_2015_Federal_Election_Votes.xlsx'), ridings)


if __name__ == '__main__':
    main(sys.argv[1])
