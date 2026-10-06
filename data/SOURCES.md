# Sources

Every file is downloaded by `python scripts/fetch_sources.py`; sizes and sha256 are in `MANIFEST.csv`. The files
themselves are not in the repository.

| source | vintage used | licence | notes |
|---|---|---|---|
| **Job Bank, job postings advertised on Canada's National Job Bank** (ESDC, open.canada.ca dataset `ea639e28-c0fc-48bf-b5dd-b8899bd43072`) | April, May and June 2026, English files | Open Government Licence – Canada | UTF-16, tab-separated; 65 columns; NOC 2021 on every row. External postings (`External Indicator` = 1) carry no education, experience or NAICS |
| **Statistics Canada, table 14-10-0444-01**, job vacancies and average offered hourly wage by occupation (unit group), quarterly, unadjusted for seasonality | 2026 Q2 (released 2026-09-15) for the comparison; 2015 Q1 to 2026 Q2 for the forecast | Statistics Canada Open Licence *(not stated in the table's metadata file; the agency's standard licence)* | DOI 10.25318/1410044401-eng. Canada, province and economic region |

## Bounds

* [BOUND] One quarter, 2026 Q2. The comparison is of shares, not counts: the survey counts vacancies over a quarter,
  while a posting is visible for days.
* [SEMANTICS] "BC health occupations" means NOC 2021 broad category 3 with Province/Territory = British Columbia.
* [BOUND] The Statistics Canada licence was not found in the downloaded metadata and is assumed from the agency's
  standard terms.
