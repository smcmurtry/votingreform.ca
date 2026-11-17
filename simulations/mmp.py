"""Mixed Member Proportional, following Wilf Day's 2015 model.

Wilf Day's model (the source of the 2015 figures on the site) is based on the
Law Commission of Canada's 2004 recommendation:

* Ridings are grouped into regions of roughly ten MPs. About 62% of a region's
  MPs are local MPs elected in enlarged ridings (eight present ridings become
  five); the rest are regional MPs elected from party lists to make the
  region's overall result proportional.
* A party with less than 2% of the vote province-wide gets no regional seats.
* A region's seats are shared among parties by largest remainder ("highest
  remainder") on the votes cast in that region.
* If a party wins more local seats than its proportional share, it keeps them,
  and the remaining seats are shared among the other parties.
* Each territory keeps its one local MP and gains one regional MP.

One step in the original was a judgement call: with eight ridings merged into
five, who wins the five? Wilf Day assigned those by hand. Here each party's
local seats are its actual riding wins in the region scaled down to the number
of local seats (largest remainder, ties to the party with more votes).
"""
import collections

from results import display, largest_remainder, party_votes

THRESHOLD = 0.02       # share of the province-wide vote needed for regional seats
LOCAL_SHARE = 0.62     # share of a region's MPs that are local (for new regions)


def local_seats(region_ridings, n_local):
    """Scale the parties' actual riding wins in a region down to n_local seats."""
    wins = collections.Counter()
    for r in region_ridings:
        wins[max(r.candidates, key=lambda c: c.votes).label] += 1
    votes = party_votes(region_ridings)
    quotients = {p: w * n_local / len(region_ridings) for p, w in wins.items()}
    out = collections.Counter({p: int(q) for p, q in quotients.items()})
    left = n_local - sum(out.values())
    order = sorted(quotients, key=lambda p: (-(quotients[p] - int(quotients[p])), -votes[p], p))
    for p in order[:left]:
        out[p] += 1
    return +out


def allocate(votes, total_seats, local):
    """Share total_seats by largest remainder, letting parties keep any local
    seats beyond their proportional share."""
    votes = dict(votes)
    fixed = collections.Counter({p: n for p, n in local.items() if p not in votes})
    while True:
        alloc = largest_remainder(votes, total_seats - sum(fixed.values()))
        over = [p for p in votes if local.get(p, 0) > alloc[p]]
        if not over:
            break
        for p in over:
            fixed[p] = local[p]
            del votes[p]
    alloc.update(fixed)
    return alloc


def simulate(ridings, region_of, region_seats):
    """region_of: {riding_number: region}; region_seats: {region: (local, regional)}.
    Returns seats [{'prov', 'party', 'district' (region), 'seat_type'}]."""
    by_prov = collections.defaultdict(list)
    by_region = collections.OrderedDict()
    for r in ridings.values():
        by_prov[r.prov].append(r)
        by_region.setdefault(region_of[r.number], []).append(r)

    eligible = {}
    for prov, rs in by_prov.items():
        total = sum(r.total for r in rs)
        eligible[prov] = set(p for p, v in party_votes(rs).items() if v >= THRESHOLD * total)

    seats = []
    for region, rs in by_region.items():
        prov = rs[0].prov
        n_local, n_regional = region_seats[region]
        local = local_seats(rs, n_local)
        votes = {p: v for p, v in party_votes(rs).items() if p in eligible[prov]}
        alloc = allocate(votes, n_local + n_regional, local)
        for p in sorted(alloc):
            for i in range(alloc[p]):
                seats.append({'prov': prov, 'party': display(p), 'district': region, 'name': region,
                              'seat_type': 'local' if i < local.get(p, 0) else 'regional'})
    return seats
