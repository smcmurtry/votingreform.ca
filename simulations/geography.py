#!/usr/bin/env python3
"""Derive riding centroids and adjacency from Elections Canada boundary shapefiles.

The simulations need to know which ridings are neighbours (to pair ridings into
DMP districts and merge them into STV districts) and roughly where each riding
is (to place the redrawn 2025 ridings in the 2015 MMP regions). This script
reads the official boundary shapefiles and writes two small CSVs per
representation order, so the shapefiles themselves do not need to be in the repo.

Boundary files (both use the same Lambert conformal conic projection, in metres):
  2013 order (2015, 2019, 2021 elections):
    https://ftp.maps.canada.ca/pub/elections_elections/Electoral-districts_Circonscription-electorale/federal_electoral_districts_boundaries_2015/federal_electoral_districts_boundaries_2015_shp_en.zip
  2023 order (2025 election):
    https://ftp.maps.canada.ca/pub/elections_elections/Electoral-districts_Circonscription-electorale/federal_electoral_districts_boundaries_2023/FED_CA_2023_EN-SHP.zip

Usage:
  python3 simulations/geography.py 2013=path/to/FED_CA_2_2_ENG.shp 2023=path/to/FED_CA_2023_EN.shp

Output in simulations/data/geography/:
  centroids_<order>.csv   riding_number, x, y, area_km2  (centroid of the largest polygon part)
  adjacency_<order>.csv   riding_a, riding_b, shared_km  (ridings sharing a land boundary)
  overlap_2023_2013.csv   for each 2023 riding, the 2013 riding that contains its centroid

Standard library only.
"""
import collections
import csv
import math
import os
import struct
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'geography')


def read_dbf(path):
    with open(path, 'rb') as f:
        data = f.read()
    n_records, header_len, record_len = struct.unpack('<IHH', data[4:12])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b'\x00')[0].decode('ascii')
        fields.append((name, data[pos + 16]))
        pos += 32
    records = []
    for i in range(n_records):
        rec = data[header_len + i * record_len: header_len + (i + 1) * record_len]
        offset = 1
        row = {}
        for name, length in fields:
            row[name] = rec[offset:offset + length].decode('utf-8', 'replace').strip()
            offset += length
        records.append(row)
    return records


def read_shp(path):
    """Yield a list of rings (each a list of (x, y)) for every polygon record."""
    with open(path, 'rb') as f:
        data = f.read()
    pos = 100
    while pos < len(data):
        content_len = struct.unpack('>i', data[pos + 4:pos + 8])[0] * 2
        rec = data[pos + 8:pos + 8 + content_len]
        pos += 8 + content_len
        shape_type = struct.unpack('<i', rec[:4])[0]
        if shape_type not in (5, 15, 25):
            yield []
            continue
        n_parts, n_points = struct.unpack('<ii', rec[36:44])
        parts = list(struct.unpack('<%di' % n_parts, rec[44:44 + 4 * n_parts])) + [n_points]
        coords = struct.unpack('<%dd' % (2 * n_points), rec[44 + 4 * n_parts:44 + 4 * n_parts + 16 * n_points])
        rings = []
        for a, b in zip(parts[:-1], parts[1:]):
            rings.append([(coords[2 * i], coords[2 * i + 1]) for i in range(a, b)])
        yield rings


def ring_area_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if a == 0:
        return 0.0, ring[0][0], ring[0][1]
    return a, cx / (6 * a), cy / (6 * a)


def point_in_ring(x, y, ring):
    inside = False
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def load(shp_path):
    dbf = read_dbf(os.path.splitext(shp_path)[0] + '.dbf')
    key = [k for k in dbf[0] if k.upper() in ('FEDNUM', 'FED_NUM', 'FEDUID', 'FED_ID')]
    if not key:
        raise SystemExit('No riding number field in %s: %s' % (shp_path, list(dbf[0])))
    ridings = {}
    for row, rings in zip(dbf, read_shp(shp_path)):
        number = int(float(row[key[0]]))
        ridings.setdefault(number, []).extend(rings)
    return ridings


def centroids(ridings):
    out = {}
    for number, rings in ridings.items():
        # Outer rings are clockwise (negative area) in shapefiles; holes are positive.
        best = min((ring_area_centroid(r) for r in rings), key=lambda t: t[0])
        total = -sum(ring_area_centroid(r)[0] for r in rings)
        out[number] = (best[1], best[2], total / 1e6)
    return out


def adjacency(ridings, min_shared_m=200.0):
    """Ridings are neighbours if they share boundary segments (matched on
    coordinates rounded to the metre) totalling at least min_shared_m."""
    owners = collections.defaultdict(set)
    for number, rings in ridings.items():
        for ring in rings:
            pts = [(round(x), round(y)) for x, y in ring]
            for p, q in zip(pts[:-1], pts[1:]):
                if p != q:
                    owners[(p, q) if p < q else (q, p)].add(number)
    shared = collections.Counter()
    for (p, q), nums in owners.items():
        if len(nums) > 1:
            length = math.hypot(p[0] - q[0], p[1] - q[1])
            nums = sorted(nums)
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    shared[(nums[i], nums[j])] += length
    return {pair: length for pair, length in shared.items() if length >= min_shared_m}


def main(args):
    os.makedirs(OUT, exist_ok=True)
    loaded = {}
    for arg in args:
        order, path = arg.split('=', 1)
        ridings = load(path)
        loaded[order] = ridings
        cents = centroids(ridings)
        with open(os.path.join(OUT, 'centroids_%s.csv' % order), 'w', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['riding_number', 'x', 'y', 'area_km2'])
            for number in sorted(cents):
                x, y, area = cents[number]
                w.writerow([number, round(x), round(y), round(area, 1)])
        adj = adjacency(ridings)
        with open(os.path.join(OUT, 'adjacency_%s.csv' % order), 'w', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['riding_a', 'riding_b', 'shared_km'])
            for (a, b) in sorted(adj):
                w.writerow([a, b, round(adj[(a, b)] / 1000, 2)])
        degree = collections.Counter()
        for a, b in adj:
            degree[a] += 1
            degree[b] += 1
        isolated = [n for n in cents if degree[n] == 0]
        print(order, len(cents), 'ridings;', len(adj), 'adjacent pairs; no neighbours:', isolated)

    if '2013' in loaded and '2023' in loaded:
        old = loaded['2013']
        boxes = {}
        for number, rings in old.items():
            xs = [x for r in rings for x, _ in r]
            ys = [y for r in rings for _, y in r]
            boxes[number] = (min(xs), min(ys), max(xs), max(ys))
        old_cents = centroids(old)
        rows = []
        for number, (x, y, _) in sorted(centroids(loaded['2023']).items()):
            match = None
            for o, (x0, y0, x1, y1) in boxes.items():
                if o // 1000 == number // 1000 and x0 <= x <= x1 and y0 <= y <= y1:
                    if sum(point_in_ring(x, y, r) for r in old[o]) % 2 == 1:
                        match = o
                        break
            how = 'contains'
            if match is None:
                same_prov = [o for o in old_cents if o // 1000 == number // 1000]
                match = min(same_prov, key=lambda o: math.hypot(old_cents[o][0] - x, old_cents[o][1] - y))
                how = 'nearest'
            rows.append([number, match, how])
        with open(os.path.join(OUT, 'overlap_2023_2013.csv'), 'w', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['riding_2023', 'riding_2013', 'method'])
            w.writerows(rows)
        print('overlap:', collections.Counter(r[2] for r in rows))


if __name__ == '__main__':
    main(sys.argv[1:])
