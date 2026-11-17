# Voting system simulations

The Python code that produces the simulated election results on
[votingreform.ca](https://votingreform.ca) for the 2019, 2021 and 2025 federal
elections. (The 2015 simulations on the site were supplied by outside
contributors and are not produced by this code.)

The methods and their assumptions are explained for a general reader at
<https://votingreform.ca/methods/>.

Everything uses the Python 3 standard library only.

## Running

```
python3 simulations/run.py              # rewrite data/2019, data/2021, data/2025
python3 simulations/run.py --validate   # run the models on 2015 and compare with
                                        # the contributors' published 2015 results
```

## What is here

| File | What it does |
|---|---|
| `run.py` | Runs every system for every election and writes the files the site reads. |
| `results.py` | Loads Elections Canada's official results. |
| `av.py` | Alternative Vote (after Éric Grenier). |
| `dmp.py` | Dual Member Proportional (Sean Graham's design, after Rhys Goldstein's simulation). |
| `mmp.py` | Mixed Member Proportional (Wilf Day's model). |
| `stv.py` | Single Transferable Vote (a new design; the 2015 method was not recorded). |
| `preferences.py` | Where ballots go when a candidate is eliminated (AV and STV). |
| `groupings.py` | Which ridings form each MMP region, DMP district and STV district. |
| `geography.py` | Derives riding centroids and neighbours from boundary shapefiles. |
| `import_2015_groupings.py` | Extracts the 2015 contributors' riding groupings from their spreadsheets. |

## Data

| Path | Contents | Source |
|---|---|---|
| `data/raw/results_<year>.csv` | Votes for every candidate in every riding | Elections Canada, Official Voting Results, table 12 |
| `data/second_choice.csv` | Second choices by first choice | Innovative Research Group; see `data/second_choice_README.md` |
| `data/geography/` | Riding centroids, neighbours, and old-to-new riding matches | Derived by `geography.py` from Elections Canada boundary files |
| `data/groupings/*_2013.csv` | MMP regions and DMP districts for the 2015-2021 ridings | Wilf Day and Rhys Goldstein, via `import_2015_groupings.py` |
| `data/groupings/*_2023.csv`, `stv_districts_*.csv` | Groupings for the 2025 ridings, and all STV districts | Derived by `groupings.py` |

## Rebuilding the derived data

These steps are only needed if the inputs change; their outputs are committed.

```
# 1. Geography, from the boundary shapefiles (URLs are in geography.py)
python3 simulations/geography.py 2013=path/to/FED_CA_2_2_ENG.shp 2023=path/to/FED_CA_2023_EN.shp

# 2. The 2015 contributors' groupings, from a checkout of github.com/smcmurtry/electoral_reform
python3 simulations/import_2015_groupings.py path/to/electoral_reform

# 3. Groupings for the 2025 ridings, and the STV districts
python3 simulations/groupings.py
```

## Adding an election

1. Save Elections Canada's table 12 as `data/raw/results_<year>.csv`.
2. Add that campaign's second-choice polling to `data/second_choice.csv`.
3. Add the year to `YEARS` in `run.py` and to `elections` in `js/common.js`.
4. If the riding boundaries changed, rerun the three steps above with the new boundary file.
