"""Single Transferable Vote in multi-member districts.

Unlike the other three, this is NOT a reconstruction of the 2015 figures on the
site. Those were supplied by Ryan Campbell as seat totals for 82 districts
averaging 4.1 MPs, without the district boundaries or counting rules. This is
an independent design in the same spirit:

* Districts are built by merging neighbouring ridings (two neighbouring DMP
  districts, so usually four ridings) and elect as many MPs as they have
  ridings. The House stays its actual size.
* A candidate needs a Droop quota: votes / (seats + 1), plus one.
* Actual votes are treated as first preferences for a party's slate. Voters
  are assumed to rank all of their party's candidates first, so a party's vote
  elects one MP per full quota and its remainder stays with its last candidate.
* When seats are left over, the candidate with the fewest votes is eliminated
  and those ballots transfer using the same second-choice polling as the
  Alternative Vote simulation, until every seat is filled.
"""
import collections

from results import display


def count_district(rs, seats, prefs):
    """Return a list of winning party labels, one per seat."""
    prov = rs[0].prov
    first = collections.Counter()   # key -> first-preference votes
    label = {}
    for r in rs:
        for i, c in enumerate(r.candidates):
            key = ('ind', r.number, i) if c.independent else c.label
            first[key] += c.votes
            label[key] = c.label
    quota = int(sum(first.values()) / (seats + 1)) + 1
    piles = {k: {label[k]: float(v)} for k, v in first.items()}
    won = []

    def total(k):
        return sum(piles[k].values())

    def transfer(k, amount):
        """Move `amount` of k's ballots on to the candidates still in the race."""
        pile = piles[k]
        size = sum(pile.values())
        if size <= 0:
            return
        remaining = [(j, label[j], first[j]) for j in piles if j != k]
        for origin, ballots in pile.items():
            moving = ballots * amount / size
            first_transfer = origin == label[k]
            for j, frac in prefs.split(origin, prov, remaining, first_transfer).items():
                piles[j][origin] = piles[j].get(origin, 0.0) + moving * frac
            pile[origin] = ballots - moving

    while len(won) < seats:
        # Elect everyone with a quota.
        elected = False
        for k in sorted(piles, key=lambda k: (-total(k), str(k))):
            while k in piles and total(k) >= quota and len(won) < seats:
                won.append(label[k])
                elected = True
                size = total(k)
                if isinstance(k, tuple):
                    # An independent's surplus moves on; a party's stays with its next candidate.
                    transfer(k, size - quota)
                    del piles[k]
                else:
                    for origin in piles[k]:
                        piles[k][origin] *= (size - quota) / size
        if len(won) >= seats:
            break
        if elected:
            continue
        if len(piles) <= seats - len(won):
            for k in sorted(piles, key=lambda k: (-total(k), str(k))):
                won.append(label[k])
            break
        loser = min(piles, key=lambda k: (total(k), first[k], str(k)))
        transfer(loser, total(loser))
        del piles[loser]
    return won[:seats]


def simulate(ridings, district_of, prefs):
    """district_of: {riding_number: district name}; seats = ridings in the district."""
    districts = collections.OrderedDict()
    for r in ridings.values():
        districts.setdefault(district_of[r.number], []).append(r)
    seats = []
    for d, rs in districts.items():
        for p in count_district(rs, len(rs), prefs):
            seats.append({'prov': rs[0].prov, 'party': display(p), 'district': d, 'name': d,
                          'seat_type': 'local'})
    return seats
