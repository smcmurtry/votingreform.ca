#!/usr/bin/env python3
"""How ridings are grouped into MMP regions, DMP districts and STV districts.

For the 2013 representation order (2015, 2019 and 2021 elections) the MMP
regions and DMP districts are the ones the original contributors drew for 2015
(see import_2015_groupings.py). Everything else is derived here from riding
geography (see geography.py) and written to data/groupings/ so it can be read:

  mmp_regions_2023.csv    The 2025 ridings placed in Wilf Day's regions: each
                          riding joins the region of the 2015-era riding that
                          contains its centre.
  dmp_districts_2023.csv  The 2025 ridings paired into two-seat districts.
  stv_districts_<order>.csv  Multi-member STV districts for both sets of
                          boundaries, made by merging neighbouring DMP districts.

Usage:
  python3 simulations/groupings.py      # rebuild the derived CSVs
"""
import collections
import csv
import math
import os

import mmp
import results

HERE = os.path.dirname(os.path.abspath(__file__))
GROUPINGS = os.path.join(HERE, 'data', 'groupings')
GEOGRAPHY = os.path.join(HERE, 'data', 'geography')

# Ridings left as their own district because of their remoteness, as in the
# original DMP model (Labrador and the three territories).
REMOTE_2023 = (10004, 60001, 61001, 62001)


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def centroids(order):
    return {int(r['riding_number']): (float(r['x']), float(r['y']))
            for r in read(os.path.join(GEOGRAPHY, 'centroids_%s.csv' % order))}


def neighbours(order):
    """{riding: set of ridings in the same province sharing a boundary}."""
    out = collections.defaultdict(set)
    for r in read(os.path.join(GEOGRAPHY, 'adjacency_%s.csv' % order)):
        a, b = int(r['riding_a']), int(r['riding_b'])
        if a // 1000 == b // 1000:
            out[a].add(b)
            out[b].add(a)
    return out


def distance(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def pair_up(nodes, adjacent, position):
    """Pair neighbouring nodes. Repeatedly take the node with the fewest
    unpaired neighbours (so that nobody is stranded) and pair it with the
    nearest of them. Then, wherever two nodes are still unpaired, look for a
    chain of swaps that pairs them both. Returns (pairs, leftover nodes)."""
    free = set(nodes)
    partner = {}
    while free:
        options = {n: [m for m in adjacent[n] if m in free] for n in free}
        n = min(free, key=lambda n: (len(options[n]) == 0, len(options[n]), n))
        free.discard(n)
        if not options[n]:
            continue
        m = min(options[n], key=lambda m: (distance(position[n], position[m]), m))
        free.discard(m)
        partner[n], partner[m] = m, n

    nodes = set(nodes)

    def augment(start):
        # Depth-first search for a path start - a = b - c = d ... - end, where
        # "=" are existing pairs and "end" is unpaired; flipping it pairs everyone on it.
        seen = set([start])

        def visit(n):
            for m in sorted(adjacent[n] & nodes, key=lambda m: (distance(position[n], position[m]), m)):
                if m in seen:
                    continue
                seen.add(m)
                if m not in partner:
                    partner[n], partner[m] = m, n
                    return True
                nxt = partner[m]
                if nxt in seen:
                    continue
                seen.add(nxt)
                if visit(nxt):
                    partner[n], partner[m] = m, n
                    return True
            return False

        return visit(start)

    improved = True
    while improved:
        improved = False
        for n in sorted(nodes):
            if n not in partner and augment(n):
                improved = True
    pairs = sorted((n, m) for n, m in partner.items() if n < m)
    leftover = sorted(n for n in nodes if n not in partner)
    return pairs, leftover


# ---------------------------------------------------------------- MMP regions

def mmp_regions(order):
    """Return ({riding: region}, {region: (local seats, regional seats)})."""
    if order == '2013':
        region_of = {int(r['riding_number']): r['region']
                     for r in read(os.path.join(GROUPINGS, 'mmp_regions_2013.csv'))}
        seats = {r['region']: (int(r['local_seats']), int(r['regional_seats']))
                 for r in read(os.path.join(GROUPINGS, 'mmp_region_seats_2013.csv'))}
        return region_of, seats
    rows = read(os.path.join(GROUPINGS, 'mmp_regions_2023.csv'))
    region_of = {int(r['riding_number']): r['region'] for r in rows}
    return region_of, mmp_region_seats(region_of)


def mmp_region_seats(region_of):
    """Seats for regions on new boundaries: as many MPs as the region has
    ridings, about 62% of them local (Wilf Day's average). Territories keep
    their local MP and gain a regional one, as in the original."""
    sizes = collections.Counter(region_of.values())
    territory = set(region for riding, region in region_of.items() if riding // 1000 >= 60)
    seats = {}
    for region, n in sizes.items():
        if region in territory:
            seats[region] = (1, 1)
        else:
            local = int(mmp.LOCAL_SHARE * n + 0.5)
            seats[region] = (local, n - local)
    return seats


def build_mmp_2023(ridings):
    old_region = {int(r['riding_number']): r['region']
                  for r in read(os.path.join(GROUPINGS, 'mmp_regions_2013.csv'))}
    rows = []
    for r in read(os.path.join(GEOGRAPHY, 'overlap_2023_2013.csv')):
        n = int(r['riding_2023'])
        rows.append([n, ridings[n].name, old_region[int(r['riding_2013'])]])
    write('mmp_regions_2023.csv', ['riding_number', 'riding_name', 'region'], rows)


# -------------------------------------------------------------- DMP districts

def dmp_districts(order):
    return {int(r['riding_number']): r['district']
            for r in read(os.path.join(GROUPINGS, 'dmp_districts_%s.csv' % order))}


def build_dmp_2023(ridings):
    """Pair neighbouring ridings within each province. A riding left without
    a partner joins the nearest neighbouring pair, making one three-riding
    district (the original had one of these, in Niagara)."""
    position = centroids('2023')
    adjacent = neighbours('2023')
    groups = []
    by_prov = collections.defaultdict(list)
    for n in ridings:
        if n in REMOTE_2023:
            groups.append([n])
        else:
            by_prov[n // 1000].append(n)
    for prov in sorted(by_prov):
        pairs, leftover = pair_up(by_prov[prov], adjacent, position)
        prov_groups = [list(p) for p in pairs]
        for n in leftover:
            touching = [g for g in prov_groups if len(g) == 2 and any(m in adjacent[n] for m in g)]
            pool = touching or prov_groups
            best = min(pool, key=lambda g: min(distance(position[n], position[m]) for m in g))
            best.append(n)
        groups.extend(prov_groups)
    rows = []
    for g in groups:
        g = sorted(g)
        name = ' + '.join(ridings[n].name.replace('--', '—') for n in g)
        for n in g:
            rows.append([n, ridings[n].name, name, ridings[n].prov])
    rows.sort()
    write('dmp_districts_2023.csv', ['riding_number', 'riding_name', 'district', 'prov'], rows)


# -------------------------------------------------------------- STV districts

def stv_districts(order):
    return {int(r['riding_number']): r['district']
            for r in read(os.path.join(GROUPINGS, 'stv_districts_%s.csv' % order))}


def build_stv(order, ridings):
    """Merge neighbouring DMP districts two at a time. A DMP district left
    without a partner becomes an STV district on its own."""
    position = centroids(order)
    adjacent = neighbours(order)
    dmp = dmp_districts(order)
    members = collections.defaultdict(list)
    for n in ridings:
        members[(ridings[n].prov, dmp[n])].append(n)
    centre = {d: (sum(position[n][0] for n in ns) / len(ns), sum(position[n][1] for n in ns) / len(ns))
              for d, ns in members.items()}
    owner = {n: d for d, ns in members.items() for n in ns}
    touching = collections.defaultdict(set)
    for n, ms in list(adjacent.items()):
        for m in ms:
            if n in owner and m in owner and owner[n] != owner[m]:
                touching[owner[n]].add(owner[m])
    rows = []
    by_prov = collections.defaultdict(list)
    for d in members:
        by_prov[d[0]].append(d)
    for prov in results.PROV_ORDER:
        pairs, leftover = pair_up(by_prov[prov], touching, centre)
        merged = [members[a] + members[b] for a, b in pairs] + [members[d] for d in leftover]
        merged.sort(key=lambda ns: min(ns))
        for i, ns in enumerate(merged):
            for n in sorted(ns):
                rows.append([n, ridings[n].name, '%s-%d' % (prov, i + 1), prov, len(ns)])
    rows.sort()
    write('stv_districts_%s.csv' % order, ['riding_number', 'riding_name', 'district', 'prov', 'seats'], rows)
    sizes = collections.Counter(r[4] for r in rows)
    print('STV %s: %d districts; ridings by district size: %s'
          % (order, len(set(r[2] for r in rows)), dict(sorted(sizes.items()))))


def write(name, header, rows):
    with open(os.path.join(GROUPINGS, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(header)
        w.writerows(rows)


def main():
    r2013 = results.load(2021)
    r2023 = results.load(2025)
    build_mmp_2023(r2023)
    build_dmp_2023(r2023)
    build_stv('2013', r2013)
    build_stv('2023', r2023)
    region_of, seats = mmp_regions('2023')
    print('MMP 2023: %d regions, %d seats' % (len(seats), sum(a + b for a, b in seats.values())))
    for region in sorted(seats, key=lambda k: -sum(seats[k])):
        print('   %-55s %2d ridings -> %d local + %d regional'
              % (region, collections.Counter(region_of.values())[region], seats[region][0], seats[region][1]))
    d = dmp_districts('2023')
    print('DMP 2023: %d districts; sizes %s'
          % (len(set(d.values())), dict(collections.Counter(collections.Counter(d.values()).values()))))


if __name__ == '__main__':
    main()
