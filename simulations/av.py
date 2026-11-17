"""Alternative Vote (instant runoff), riding by riding.

Follows the approach Éric Grenier used for the 2015 figures on the site: keep
the existing ridings, take the actual votes as first choices, and use
second-choice polling to redistribute the votes of eliminated candidates until
someone has a majority of the ballots still in play.
"""
from results import display


def count_riding(riding, prefs):
    """Return the winning candidate's party label."""
    # piles[candidate key] = {first-choice label of the ballots: number of ballots}
    cands = {i: c for i, c in enumerate(riding.candidates)}
    piles = {i: {c.label: float(c.votes)} for i, c in cands.items()}
    while True:
        totals = {i: sum(p.values()) for i, p in piles.items()}
        in_play = sum(totals.values())
        leader = max(totals, key=lambda i: (totals[i], cands[i].votes))
        if len(totals) == 1 or totals[leader] > in_play / 2:
            return cands[leader].label
        loser = min(totals, key=lambda i: (totals[i], cands[i].votes))
        pile = piles.pop(loser)
        remaining = [(i, cands[i].label, cands[i].votes) for i in piles]
        for origin, ballots in pile.items():
            # Ballots are tracked by the party they were first cast for. Voters
            # with no second choice drop out the first time their ballot moves.
            first_transfer = origin == cands[loser].label
            for i, frac in prefs.split(origin, riding.prov, remaining, first_transfer).items():
                piles[i][origin] = piles[i].get(origin, 0.0) + ballots * frac


def simulate(ridings, prefs):
    """Return one seat per riding: [{'prov', 'party', 'district', 'seat_type'}]."""
    seats = []
    for r in ridings.values():
        seats.append({'prov': r.prov, 'party': display(count_riding(r, prefs)),
                      'district': r.number, 'name': r.name, 'seat_type': 'local'})
    return seats
