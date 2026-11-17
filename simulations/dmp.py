"""Dual Member Proportional, following Sean Graham's design as simulated for
2015 by Rhys Goldstein (the source of the 2015 figures on the site).

* Ridings are merged, mostly in pairs, into districts that each elect two MPs.
* Each province is a region. Its seats (two per district) are shared among
  parties by largest remainder on the province-wide vote. A party needs 3% of
  the province's vote to take part. (The 2015 results imply this threshold:
  the Greens won a seat in Manitoba with 3.2% and none in Ontario with 2.8%.)
* The first seat in every district goes to the candidate with the most votes.
* Each party's remaining seats are then placed in the districts where it did
  best. A party that already holds a district's first seat competes for the
  second with half its vote share (its second candidate). When two parties
  want the same second seat, the one with the higher share gets it and the
  other moves on to its next-best district.
* An independent wins a seat by finishing first or second in a district.
* A party that wins more first seats than its proportional share keeps them.

In a merged district each party's votes are the sum of its votes in the
ridings that make it up.
"""
import collections

from results import display, largest_remainder

THRESHOLD = 0.03


def simulate(ridings, district_of):
    """district_of: {riding_number: district name}.
    Returns two seats per district: [{'prov', 'party', 'district', 'seat_type'}]."""
    regions = collections.OrderedDict()
    for r in ridings.values():
        regions.setdefault(r.prov, collections.OrderedDict()).setdefault(district_of[r.number], []).append(r)

    seats = []
    for prov, districts in regions.items():
        votes = {}     # district -> {key: votes}; key is a party label or ('ind', riding, i)
        for d, rs in districts.items():
            v = collections.Counter()
            for r in rs:
                for i, c in enumerate(r.candidates):
                    v[('ind', r.number, i) if c.independent else c.label] += c.votes
            votes[d] = v
        totals = {d: sum(v.values()) for d, v in votes.items()}
        share = {d: {k: n / totals[d] for k, n in v.items()} for d, v in votes.items()}

        first = {}
        second = {}
        for d, v in votes.items():
            ranked = sorted(v, key=lambda k: (-v[k], str(k)))
            first[d] = ranked[0]
            if len(ranked) > 1 and isinstance(ranked[1], tuple):
                second[d] = ranked[1]      # an independent in second place

        region_total = sum(totals.values())
        party = collections.Counter()
        for v in votes.values():
            for k, n in v.items():
                if not isinstance(k, tuple):
                    party[k] += n
        eligible = {p: n for p, n in party.items() if n >= THRESHOLD * region_total}

        first_won = collections.Counter(k for k in first.values() if not isinstance(k, tuple))
        independents = sum(1 for k in list(first.values()) + list(second.values()) if isinstance(k, tuple))
        available = 2 * len(districts) - independents
        # Parties below the threshold, or with more first seats than their share, keep what they won.
        fixed = collections.Counter({p: n for p, n in first_won.items() if p not in eligible})
        pool = dict(eligible)
        while True:
            alloc = largest_remainder(pool, available - sum(fixed.values()))
            over = [p for p in pool if first_won[p] > alloc[p]]
            if not over:
                break
            for p in over:
                fixed[p] = first_won[p]
                del pool[p]
        need = {p: alloc[p] - first_won[p] for p in pool}

        # Each party's candidates for second seats, best first.
        prefs = {}
        for p in pool:
            ranked = []
            for d in districts:
                if d in second or p not in share[d]:
                    continue
                s = share[d][p] / 2 if first[d] == p else share[d][p]
                ranked.append((s, d))
            ranked.sort(key=lambda t: (-t[0], str(t[1])))
            prefs[p] = ranked
        position = {p: 0 for p in pool}
        holder = {}    # district -> (share, party) tentatively holding the second seat
        waiting = [p for p in sorted(pool) for _ in range(need[p])]
        while waiting:
            p = waiting.pop()
            if position[p] >= len(prefs[p]):
                continue               # the party has run out of districts
            s, d = prefs[p][position[p]]
            position[p] += 1
            if d not in holder:
                holder[d] = (s, p)
            elif (s, votes[d][p]) > (holder[d][0], votes[d][holder[d][1]]):
                waiting.append(holder[d][1])
                holder[d] = (s, p)
            else:
                waiting.append(p)
        for d, (_, p) in holder.items():
            second[d] = p
        # Any second seat still empty goes to the best-placed party candidate there.
        for d in districts:
            if d not in second:
                options = [(share[d][p] / 2 if first[d] == p else share[d][p], p)
                           for p in share[d] if not isinstance(p, tuple)]
                second[d] = max(options)[1]

        for d in districts:
            for k in (first[d], second[d]):
                seats.append({'prov': prov, 'district': d, 'name': d, 'seat_type': 'local',
                              'party': 'Other' if isinstance(k, tuple) else display(k)})
    return seats
