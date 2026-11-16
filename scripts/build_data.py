#!/usr/bin/env python3
"""Build the per-election data files used by the site.

Input: Elections Canada "Official Voting Results" table 12 (list of candidates
by electoral district, with votes obtained), one CSV per general election:

  2019: https://www.elections.ca/res/rep/off/ovr2019app/51/data_donnees/table_tableau12.csv
  2021: https://www.elections.ca/res/rep/off/ovr2021app/53/data_donnees/table_tableau12.csv
  2025: https://www.elections.ca/res/rep/off/ovrGE45/62/data_donnees/table_tableau12.csv

Usage:
  python3 scripts/build_data.py 2019=path/to/2019_t12.csv 2021=... 2025=...

Output, for each year, in data/<year>/ (same formats as the 2015 files in data/):
  fptp_clean.csv    one row per riding with the winning party
  tot_summary.json  seats by party, by region
  pct_summary.csv   share of seats (FPTP) and share of the vote (POP) by party, by region
and data/elections_summary.json with national vote and seat totals for every
election (including 2015), used by the summary table at the top of the page.
"""
import collections
import csv
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA = os.path.join(ROOT, 'data')

PARTIES = ['Liberal', 'Conservative', 'NDP', 'Bloc', 'Green', 'Other']

# Province name (English part) -> abbreviation and the region_number used by the 2015 files.
PROVS = {
    'British Columbia': ('BC', 0), 'Alberta': ('AB', 1), 'Saskatchewan': ('SK', 2),
    'Manitoba': ('MB', 3), 'Ontario': ('ON', 4), 'Quebec': ('QC', 5),
    'New Brunswick': ('NB', 6), 'Nova Scotia': ('NS', 7), 'Prince Edward Island': ('PE', 8),
    'Newfoundland and Labrador': ('NL', 9), 'Yukon': ('YT', 10),
    'Northwest Territories': ('NT', 11), 'Nunavut': ('NU', 12),
}
REGIONS = ['Canada'] + [abbr for abbr, _ in PROVS.values()]

# The candidate field ends with the party name, in English and French.
PARTY_SUFFIXES = [
    ('Liberal/Libéral', 'Liberal'),
    ('Conservative/Conservateur', 'Conservative'),
    ('NDP-New Democratic Party/NPD-Nouveau Parti démocratique', 'NDP'),
    ('Bloc Québécois/Bloc Québécois', 'Bloc'),
    ('Green Party/Parti Vert', 'Green'),
]


def party_of(candidate):
    for suffix, party in PARTY_SUFFIXES:
        if candidate.endswith(suffix):
            return party
    return 'Other'


def build_year(year, path):
    votes = {r: collections.Counter() for r in REGIONS}
    seats = {r: collections.Counter() for r in REGIONS}
    ridings = collections.OrderedDict()  # number -> (name, prov, best votes, best party)

    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            prov, _ = PROVS[row[0].split('/')[0]]
            name, number, candidate, n = row[1], int(row[2]), row[3], int(row[6])
            party = party_of(candidate)
            votes[prov][party] += n
            votes['Canada'][party] += n
            if number not in ridings or n > ridings[number][2]:
                ridings[number] = (name, prov, n, party)

    for name, prov, _, party in ridings.values():
        seats[prov][party] += 1
        seats['Canada'][party] += 1

    out = os.path.join(DATA, str(year))
    os.makedirs(out, exist_ok=True)

    region_number = {abbr: n for abbr, n in PROVS.values()}
    with open(os.path.join(out, 'fptp_clean.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['riding_name', 'riding_number', 'party', 'prov_abbr', 'region_number', 'seat_type'])
        for number, (name, prov, _, party) in ridings.items():
            w.writerow([name, number, party, prov, region_number[prov], 'local'])

    tot = {r: {'FPTP': {p: seats[r][p] for p in PARTIES}} for r in REGIONS}
    with open(os.path.join(out, 'tot_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(tot, f)

    with open(os.path.join(out, 'pct_summary.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['party', 'region', 'voting_system', 'value'])
        for r in REGIONS:
            total_votes = sum(votes[r].values())
            total_seats = sum(seats[r].values())
            for p in PARTIES:
                w.writerow([p, r, 'POP', round(votes[r][p] / total_votes, 5)])
            for p in PARTIES:
                w.writerow([p, r, 'FPTP', round(seats[r][p] / total_seats, 5)])

    total_votes = sum(votes['Canada'].values())
    total_seats = sum(seats['Canada'].values())
    return {
        'total_seats': total_seats,
        'seats': {p: seats['Canada'][p] for p in PARTIES},
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
    return {
        'total_seats': sum(seats.values()),
        'seats': {p: int(seats[p]) for p in PARTIES},
        'vote_share': {p: share[p] for p in PARTIES},
    }


def main(args):
    summary = {'2015': summary_2015()}
    for arg in args:
        year, path = arg.split('=', 1)
        summary[year] = build_year(int(year), path)
        print(year, summary[year])
    with open(os.path.join(DATA, 'elections_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=1, sort_keys=True)


if __name__ == '__main__':
    main(sys.argv[1:])
