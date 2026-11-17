#!/usr/bin/env python3
"""Run the simulations and write the data files the site reads.

Usage:
  python3 simulations/run.py              # write data/<year>/ for 2019, 2021, 2025
  python3 simulations/run.py --validate   # compare the models' 2015 output with the
                                          # contributors' 2015 results used on the site

For each election this writes, in data/<year>/ (same formats as the 2015 files in data/):
  fptp_clean.csv, irv_clean.csv, dmp_clean.csv, mmp_clean.csv, stv_clean.csv
      one row per seat
  tot_summary.json   seats by party, by region and voting system
  pct_summary.csv    share of seats for each system, and share of the vote (POP)
and data/elections_summary.json with national totals for every election.
"""
import collections
import csv
import json
import os
import sys

import av
import dmp
import groupings
import mmp
import results
import stv
from preferences import Preferences

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA = os.path.join(ROOT, 'data')
PARTIES = results.PARTIES
REGIONS = ['Canada'] + results.PROV_ORDER
YEARS = [2019, 2021, 2025]
SYSTEMS = ['FPTP', 'IRV', 'DMP', 'MMP', 'STV']   # IRV is the site's code for Alternative Vote


def fptp(ridings):
    return [{'prov': r.prov, 'party': r.winner, 'district': r.number, 'name': r.name, 'seat_type': 'local'}
            for r in ridings.values()]


def simulate(year, prefs_year=None):
    """Return ({system: seats}, ridings). prefs_year lets one election borrow
    another's second-choice polling (used only for validating against 2015)."""
    ridings = results.load(year)
    order = results.order_of(year)
    prefs = Preferences(prefs_year or year, ridings)
    region_of, region_seats = groupings.mmp_regions(order)
    out = collections.OrderedDict()
    out['FPTP'] = fptp(ridings)
    out['IRV'] = av.simulate(ridings, prefs)
    out['DMP'] = dmp.simulate(ridings, groupings.dmp_districts(order))
    out['MMP'] = mmp.simulate(ridings, region_of, region_seats)
    out['STV'] = stv.simulate(ridings, groupings.stv_districts(order), prefs)
    return out, ridings


def tally(seats):
    """{region: {party: seats}} including Canada."""
    out = {r: collections.Counter() for r in REGIONS}
    for s in seats:
        out[s['prov']][s['party']] += 1
        out['Canada'][s['party']] += 1
    return out


def write_seats(path, seats):
    """One row per seat. riding_number groups the seats drawn inside one
    border on the site's seat chart; region_number groups them into blocks."""
    prov_index = {p: i for i, p in enumerate(results.PROV_ORDER)}
    district_ids = {}
    region_ids = {}
    rows = []
    for s in seats:
        key = (s['prov'], s['district'])
        if os.path.basename(path) == 'mmp_clean.csv':
            # Under MMP every MP is drawn in a box of their own (local MPs each
            # have a riding; regional MPs are drawn without a border).
            riding_number = len(rows)
        else:
            riding_number = district_ids.setdefault(key, len(district_ids))
        rows.append((s, riding_number))
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['riding_name', 'riding_number', 'party', 'prov_abbr', 'region_number', 'seat_type'])
        for s, riding_number in rows:
            if os.path.basename(path) == 'mmp_clean.csv':
                region = region_ids.setdefault((s['prov'], s['district']), len(region_ids))
            else:
                region = prov_index[s['prov']]
            w.writerow([s['name'], riding_number, s['party'], s['prov'], region, s['seat_type']])


def write_year(year):
    systems, ridings = simulate(year)
    out = os.path.join(DATA, str(year))
    os.makedirs(out, exist_ok=True)

    # MMP regions are numbered in the site's province order so they draw together.
    order = {p: i for i, p in enumerate(results.PROV_ORDER)}
    systems['MMP'].sort(key=lambda s: (order[s['prov']], s['district'], s['seat_type'], PARTIES.index(s['party'])))
    names = {'FPTP': 'fptp', 'IRV': 'irv', 'DMP': 'dmp', 'MMP': 'mmp', 'STV': 'stv'}
    for system, seats in systems.items():
        write_seats(os.path.join(out, names[system] + '_clean.csv'), seats)

    votes = {r: collections.Counter() for r in REGIONS}
    for r in ridings.values():
        votes[r.prov].update(r.votes)
        votes['Canada'].update(r.votes)
    tallies = {system: tally(seats) for system, seats in systems.items()}

    tot = {region: {system: {p: tallies[system][region][p] for p in PARTIES} for system in SYSTEMS}
           for region in REGIONS}
    with open(os.path.join(out, 'tot_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(tot, f)

    with open(os.path.join(out, 'pct_summary.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['party', 'region', 'voting_system', 'value'])
        for region in REGIONS:
            total_votes = sum(votes[region].values())
            for p in PARTIES:
                w.writerow([p, region, 'POP', round(votes[region][p] / total_votes, 5)])
            for system in SYSTEMS:
                total_seats = sum(tallies[system][region].values())
                for p in PARTIES:
                    w.writerow([p, region, system, round(tallies[system][region][p] / total_seats, 5)])

    total_votes = sum(votes['Canada'].values())
    print(year)
    for system in SYSTEMS:
        t = tallies[system]['Canada']
        print('  %-5s %s  total %d' % (system, '  '.join('%s %3d' % (p[:4], t[p]) for p in PARTIES), sum(t.values())))
    return {
        'total_seats': len(ridings),
        'seats': {p: tallies['FPTP']['Canada'][p] for p in PARTIES},
        'vote_share': {p: round(votes['Canada'][p] / total_votes, 5) for p in PARTIES},
    }


def summary_2015():
    """National 2015 figures, read from the original 2015 data files."""
    with open(os.path.join(DATA, 'tot_summary.json'), encoding='utf-8') as f:
        seats = json.load(f)['Canada']['FPTP']
    share = {}
    with open(os.path.join(DATA, 'pct_summary.csv'), encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            if row['region'] == 'Canada' and row['voting_system'] == 'POP':
                share[row['party']] = round(float(row['value']), 5)
    return {'total_seats': int(sum(seats.values())),
            'seats': {p: int(seats[p]) for p in PARTIES},
            'vote_share': {p: share[p] for p in PARTIES}}


def validate():
    """Run the models on the 2015 election and compare with the contributors'
    results, which are what the site shows for 2015."""
    with open(os.path.join(DATA, 'tot_summary.json'), encoding='utf-8') as f:
        published = json.load(f)
    # No second-choice table survives for 2015, so borrow the 2019 poll.
    systems, _ = simulate(2015, prefs_year=2019)
    report = {}
    for system in SYSTEMS:
        mine = tally(systems[system])
        print('\n%s: national seats (model / published 2015)' % system)
        for p in PARTIES:
            print('   %-13s %4d / %4d' % (p, mine['Canada'][p], published['Canada'][system][p]))
        diff = sum(abs(mine[r][p] - published[r][system][p]) for r in results.PROV_ORDER for p in PARTIES) / 2
        total = sum(published['Canada'][system].values())
        print('   seats placed differently, summed over provinces: %d of %d' % (diff, total))
        report[system] = {'model': {p: mine['Canada'][p] for p in PARTIES},
                          'published': {p: int(published['Canada'][system][p]) for p in PARTIES},
                          'seats_different_by_province': int(diff), 'total_seats': int(total)}
    return report


def main(args):
    if '--validate' in args:
        validate()
        return
    summary = {'2015': summary_2015()}
    for year in YEARS:
        summary[str(year)] = write_year(year)
    with open(os.path.join(DATA, 'elections_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=1, sort_keys=True)


if __name__ == '__main__':
    main(sys.argv[1:])
