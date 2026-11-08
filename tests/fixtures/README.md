# Parsing fixtures

Public bookstore responses captured on 2026-10-03 (Asia/Seoul):

- YES24 Goods `125557465`, ISBN `9791171711673` and ISBN search.
- Kyobo Product `S000000610625`, ISBN `9788936434267`, ISBN search and product middle API.

Fixtures preserve bibliographic fields and response structures. Long introductions and reviews were shortened. Kyobo uses Next.js Flight JSON string chunks; the adapter selects only the requested product ID.

`tests/catalog.py` builds additional **synthetic** responses for all three stores.
The domestic, foreign, and discontinued catalogue entries test title/ISBN searches,
ISBN-10 equivalence, stale store IDs, wrong editions, and diagnostics. Titles and
ISBNs are illustrative; availability, publisher, and introduction fields are made
up and do not describe the books' actual sales status. No live responses or
credentials are saved by these tests. `scripts/regression_calibre.py` runs the same
catalogue through the real Calibre loader and Metadata class with fake HTTP only.

`kyobo_api_info.json` and `kyobo_api_top.json` are reduced public API responses
captured on 2026-11-02 for product `S000221151022` (ISBN `9791124073483`).
Unneeded fields and additional writers were removed. They reproduce API recovery
when every detail HTML request returns an empty body. Tests also mutate the
product ID, ISBN, and error envelope to verify that mismatched responses are rejected.
