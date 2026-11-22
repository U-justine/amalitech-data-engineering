# Dare Careers Dashboard — Test Results

[Back to README](../README.md) · [Project Report](Project_Report.pdf) · [Data Model](Data_Model.md) · [DAX Measures](DAX_Measures.txt) · [Power Query](PowerQuery_M_Code.txt) · [Test Results](Test_Results.md)

Expected values were calculated independently from the raw source files and compared with the dashboard.

**How each test was run:** tests 1–10b and 12 were run in Power BI by applying the slicers shown; test 16 was checked in Power Query; tests 13–15 were verified against the source data; test 11 is expected from the Labs Missed measure logic.

## Page 1: Overall Performance

| # | Slicers | Expected cards (Learners / Graduations / Certifications / Dropouts) | Result |
|---|---|---|---|
| 1 | None | 140 / 119 / 92 / 7 | Pass |
| 2 | Track = AWS Cloud | 40 / 33 / 24 / 7 | Pass |
| 3 | Track = Power BI | 100 / 86 / 68 / 0 | Pass |
| 4 | Certification Status = Not Certified | 48 / 27 / 0 / 7 (AWS dropout rate 43.8%) | Pass |
| 5 | Certification Type = Power BI | 100 / 86 / 68 / 0 | Pass |
| 6 | Track = AWS Cloud + Not Certified | 16 / 9 / 0 / 7 | Pass |
| 7 | Track = Power BI + Not Certified | 32 / 18 / 0 / 0 | Pass |

Chart values with no filters (AWS Cloud / Power BI): Graduation 82.5% / 86.0% · Certification 60.0% / 68.0% · Dropout 17.5% / 0.0% · Attendance 79.3% / 100.0% · Participation 89.2% / 85.1% · Avg Score 51.8 / 50.4.

## Page 2: Learner Insights

| # | Slicers | Expected | Result |
|---|---|---|---|
| 8 | None | Labs 1,383 · Avg Labs 9.9 · Hours 10,565.7 · Attendance 94% · Participation 86% · Score 50.8 | Pass |
| 9 | Track = AWS Cloud | Labs 396 · Hours 1,813.0 · Attendance 79% · Participation 89% · Score 51.8 | Pass |
| 10 | Track = Power BI | Labs 987 · Hours 8,752.7 · Attendance 100% · Participation 85% · Score 50.4 | Pass |
| 10b | Synced slicers: Track set on Page 2, checked on Page 1 | Page 1 shows Power BI: 100 / 86 / 68 / 0 | Pass |
| 11 | Week = Week 10 | Each learner shows 1 lab (or 0); no false orange highlight | Expected (measure logic) |
| 12 | Table sort | John Miller (62%) first; 7 learners below 75% in red | Pass |

## Data and logic checks

| # | Check | Expected | Result |
|---|---|---|---|
| 13 | Learners where Is Dropout = TRUE | 7 rows, all AWS Cloud, Non Graduate, Not Certified | Pass (source data) |
| 14 | Power BI non-graduates | 14 rows, Is Dropout = FALSE (no session of 30 minutes or less) | Pass (source data) |
| 15 | Attendance where Minutes ≤ 30 | Attended = 0 on every row | Pass (source data) |
| 16 | Participation Week and Email | Week 1–10, no nulls | Pass (Power Query) |
| 17 | No rate above 100% in any test | — | Pass |

## Bug found and fixed

Certification Rate showed **212.5%** with Track = Power BI and Certification Status = Not Certified. `CALCULATE` replaced the slicer filter on the same column. Fixed by wrapping the condition in `KEEPFILTERS` (Total Graduations, Total Certifications, Total Dropouts).
