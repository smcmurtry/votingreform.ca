# Second-choice polling

`second_choice.csv` holds, for each election, the share (%) of each party's
supporters who named each other party as their second choice. Rows are the
first-choice party, columns the second choice.

All three tables come from Innovative Research Group's campaign tracking
surveys, which asked decided voters "And which party would be your second
choice?" and published the answer by first choice:

| Election | Report | Published |
|---|---|---|
| 2019 | 2019 Federal Election: Political Landscape Tracking (slide "2nd Choice by 1st Choice") | 18 October 2019 |
| 2021 | Federal Politics: Tracking, September 2021 (slide "Federal 2nd Choice") | September 2021 (field 10-12 September) |
| 2025 | Canada This Month, April 2025, wave 2 federal election deck (slide "Federal 2nd Choice Party") | April 2025 |

Reports: https://innovativeresearch.ca/

Adjustments made when transcribing:

* 2019: the poll lists the People's Party and "Other" separately as second
  choices; they are added together here as `Other`. The first-choice column
  "PPC/Other" is the `Other` row.
* 2025: the poll does not report second choices for people whose first choice
  was a party outside the main five ("insufficient sample size"). The 2021
  `Other` row is reused for 2025.
* The figures are national, with the Bloc Québécois asked only in Quebec. The
  simulations concentrate the Bloc share on Quebec voters (see `preferences.py`).
* Columns do not always sum to exactly 100 because the published figures are rounded.
