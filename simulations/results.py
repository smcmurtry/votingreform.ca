"""Load Elections Canada official voting results (table 12: candidates by riding)."""
import collections
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')

PARTIES = ['Liberal', 'Conservative', 'NDP', 'Bloc', 'Green', 'Other']

# Province name (English part) -> abbreviation, and the order used by the site.
PROVS = collections.OrderedDict([
    ('British Columbia', 'BC'), ('Alberta', 'AB'), ('Saskatchewan', 'SK'),
    ('Manitoba', 'MB'), ('Ontario', 'ON'), ('Quebec', 'QC'),
    ('New Brunswick', 'NB'), ('Nova Scotia', 'NS'), ('Prince Edward Island', 'PE'),
    ('Newfoundland and Labrador', 'NL'), ('Yukon', 'YT'),
    ('Northwest Territories', 'NT'), ('Nunavut', 'NU'),
])
PROV_ORDER = list(PROVS.values())
TERRITORIES = ('YT', 'NT', 'NU')

# The candidate field ends with the party name, in English and French.
PARTY_SUFFIXES = [
    ('Liberal/Libéral', 'Liberal'),
    ('Conservative/Conservateur', 'Conservative'),
    ('NDP-New Democratic Party/NPD-Nouveau Parti démocratique', 'NDP'),
    ('Bloc Québécois/Bloc Québécois', 'Bloc'),
    ('Green Party/Parti Vert', 'Green'),
]
INDEPENDENT_SUFFIXES = ('Independent/Indépendant(e)', 'Independent/Indépendant',
                        'No Affiliation/Aucune appartenance')


def party_of(candidate):
    """Return (label, display, is_independent) for a candidate field.

    label identifies the party in the simulations: one of the five main parties,
    the party's own name for a smaller party (so that, say, the People's Party
    is treated as one party that can cross a threshold), or 'Independent'.
    display is what the site shows: a main party, or 'Other'.
    """
    for suffix, party in PARTY_SUFFIXES:
        if candidate.endswith(suffix):
            return party, party, False
    if candidate.endswith(INDEPENDENT_SUFFIXES):
        return 'Independent', 'Other', True
    return candidate.rsplit('/', 1)[-1].strip(), 'Other', False


def display(label):
    return label if label in PARTIES else 'Other'


class Candidate(object):
    def __init__(self, label, votes, independent, riding):
        self.label = label          # party label, or 'Independent'
        self.votes = votes
        self.independent = independent
        self.riding = riding        # riding number

    @property
    def display(self):
        return display(self.label)


class Riding(object):
    """One riding's results: a list of candidates plus some conveniences."""

    def __init__(self, number, name, prov):
        self.number = number
        self.name = name
        self.prov = prov
        self.candidates = []

    @property
    def total(self):
        return sum(c.votes for c in self.candidates)

    @property
    def votes(self):
        """Votes by display party (smaller parties and independents pooled as 'Other')."""
        out = collections.Counter()
        for c in self.candidates:
            out[c.display] += c.votes
        return out

    @property
    def winner(self):
        return max(self.candidates, key=lambda c: c.votes).display


def load(year):
    """Return {riding_number: Riding} for a general election year."""
    ridings = collections.OrderedDict()
    path = os.path.join(RAW, 'results_%d.csv' % year)
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            prov = PROVS[row[0].split('/')[0]]
            number = int(row[2])
            if number not in ridings:
                ridings[number] = Riding(number, row[1].split('/')[0], prov)
            label, _, independent = party_of(row[3])
            ridings[number].candidates.append(Candidate(label, int(row[6]), independent, number))
    return ridings


def party_votes(ridings):
    """Votes by party label over a collection of ridings, leaving out independents."""
    out = collections.Counter()
    for r in ridings:
        for c in r.candidates:
            if not c.independent:
                out[c.label] += c.votes
    return out


def largest_remainder(votes, seats):
    """Share seats in proportion to votes: whole quotas first, then the largest
    remainders (the Hare quota / Hamilton method)."""
    total = sum(votes.values())
    out = collections.Counter()
    if seats <= 0 or total <= 0:
        return out
    quotients = {p: v * seats / total for p, v in votes.items()}
    for p, q in quotients.items():
        out[p] = int(q)
    left = seats - sum(out.values())
    # Ties are broken by total votes, then by name, so results are reproducible.
    order = sorted(quotients, key=lambda p: (-(quotients[p] - int(quotients[p])), -votes[p], p))
    for p in order[:left]:
        out[p] += 1
    return out


def order_of(year):
    """Representation order (riding boundaries) in force at an election."""
    return '2023' if year >= 2025 else '2013'
