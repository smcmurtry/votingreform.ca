"""Where a voter's ballot goes when their first choice is out of the race.

Used by the Alternative Vote and Single Transferable Vote simulations. Second
choices come from published polling (see data/second_choice_README.md).

Assumptions:

* Every supporter of a party has the same second-choice pattern everywhere in
  the country, with one exception: the polls report national figures, but the
  Bloc Québécois only runs in Quebec. A party's Bloc second-choice share is
  therefore concentrated on its Quebec voters (divided by the fraction of that
  party's national vote cast in Quebec), and dropped elsewhere.
* Supporters who told the pollster they were undecided about a second choice,
  or had none, do not rank anyone else: their ballot is exhausted when their
  first choice is eliminated.
* If a voter's second choice is no longer in the race (or never ran in their
  riding), they move to one of the parties still in the race, in proportion to
  the second-choice shares of those parties.
* Supporters of smaller parties and independents all share the poll's "Other"
  pattern. A second choice of "Other" goes to the remaining smaller-party and
  independent candidates in proportion to their own first-choice votes.
"""
import collections
import csv
import os

from results import PARTIES, display

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = PARTIES[:5]


class Preferences(object):
    def __init__(self, year, ridings):
        self.table = {}
        with open(os.path.join(HERE, 'data', 'second_choice.csv'), encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                if int(row['year']) == year:
                    self.table[row['first_choice']] = {p: float(row[p]) / 100 for p in PARTIES}
                    self.table[row['first_choice']]['exhausted'] = (
                        float(row['undecided']) + float(row['would_not_vote'])) / 100
        if not self.table:
            raise ValueError('No second-choice data for %d' % year)
        # Fraction of each party's national vote that was cast in Quebec.
        national = collections.Counter()
        quebec = collections.Counter()
        for r in ridings.values():
            for c in r.candidates:
                national[c.display] += c.votes
                if r.prov == 'QC':
                    quebec[c.display] += c.votes
        self.quebec_fraction = {p: quebec[p] / national[p] for p in national if national[p]}

    def shares(self, first, prov):
        """Second-choice shares over PARTIES, plus 'exhausted', for supporters
        of display party `first` living in `prov`."""
        row = dict(self.table[display(first)])
        named = sum(row[p] for p in PARTIES)
        bloc = row['Bloc']
        if bloc and named > bloc:
            if prov == 'QC':
                new_bloc = min(bloc / self.quebec_fraction.get(display(first), 1.0), 0.6 * named)
            else:
                new_bloc = 0.0
            scale = (named - new_bloc) / (named - bloc)
            for p in PARTIES:
                row[p] *= scale
            row['Bloc'] = new_bloc
        elif prov != 'QC':
            row['Bloc'] = 0.0
        return row

    def split(self, first, prov, remaining, first_transfer):
        """Split one unit of `first`'s ballots among the remaining candidates.

        remaining: list of (key, label, first_choice_votes) still in the race.
        first_transfer: True the first time these ballots move (when voters
            without a second choice drop out).
        Returns {key: fraction}; fractions sum to less than 1 if ballots exhaust.
        """
        row = self.shares(first, prov)
        weights = {}
        others = [(k, v) for k, label, v in remaining if display(label) == 'Other']
        other_votes = sum(v for _, v in others)
        for key, label, _ in remaining:
            if label in MAIN:
                weights[key] = row[label]
        for key, v in others:
            weights[key] = row['Other'] * (v / other_votes) if other_votes else 0.0
        total = sum(weights.values())
        if total <= 0:
            return {}
        keep = (1.0 - row['exhausted']) if first_transfer else 1.0
        return {k: keep * w / total for k, w in weights.items() if w > 0}
