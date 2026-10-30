# Reflection: OLTP vs Star Schema

I ran everything on my laptop with PostgreSQL 18.6 and pgAdmin. The data was 1,000,004 encounters, 2.5 million diagnosis rows, 2 million procedure rows and 900,411 claims. Each time below is the middle value of three runs, and every star query returns exactly the same result as its OLTP version.

| Query | OLTP | Star | Speedup |
|---|---|---|---|
| Q1 Monthly encounters by specialty | 4.81 s | 1.98 s | 2.4x |
| Q2 Top diagnosis-procedure pairs (bridges) | 12.08 s | 3.41 s | 3.5x |
| Q2 using the summary table | 12.08 s | 0.089 s | ~136x |
| Q3 30-day readmission rate | 0.83 s | 0.21 s | 3.9x |
| Q4 Revenue by specialty and month | 1.49 s | 1.20 s | 1.2x |

## Why is the star schema faster?

**Fewer and cheaper joins.** In the OLTP schema the specialty is always two steps away from an encounter (encounters → providers → specialties), and three steps away from a claim (billing → encounters → providers → specialties). In my star schema, `specialty_key` sits directly on the fact row. Q3 went from 3 joins (one of them a self-join) to 1, and Q4 from 3 joins to 2. Q1 actually has one more join than before, but that doesn't matter: the OLTP joins run on a million rows, while the star joins only touch the 1,296 final rows. I learned that what you join matters more than how many joins you have.

**Work done once in the ETL instead of in every query.** This made the biggest difference:

- The readmission self-join runs once during the load, and the result is stored as `is_readmitted_30d`. Q3 just counts a flag, using a partial index that only holds the 150,393 inpatient stays.
- All diagnosis-procedure pairs are counted once and stored in `agg_dx_px_pair`. Q2 then reads the top 10 rows from an index (0.79 ms of real database work).
- Billing is summed per visit (`total_allowed_amount`, `claim_count`), so Q4 never touches the billing table.
- The date key is a number like 20240510, so the month is just `date_key / 100` instead of `date_trunc()` or `TO_CHAR()` on every row.

**Why denormalization helps analytics.** Normalization is designed for writing single rows safely: each fact is stored once, so updates can't contradict each other. Reports do the opposite. They read millions of rows and return a few hundred. Copying the specialty onto every encounter and storing totals on the row means each report does far less work. The clearest example in PostgreSQL is `COUNT(DISTINCT)`, which always has to sort. In OLTP Q1 and Q2 those sorts were on text columns and spilled to disk. In the star schema I grouped on small integers, and because duplicates were removed in the ETL, Q2 can use a plain `COUNT(*)`.

**What surprised me.** The star schema alone doesn't make a query fast. My first version of star Q4 was *slower* than OLTP (2.24 s vs 1.49 s). It joined the dimensions first and grouped by text labels, so PostgreSQL had to sort 900,000 rows on text and wrote about 35 MB to disk. When I rewrote it to group on the integer keys first and add the names at the end, it dropped to 1.20 s. So the speed comes from three things together: values calculated in the ETL, integer keys on the fact table, and writing the queries so they group before they join.

## Trade-offs: what did I gain and what did I lose?

**What I lost:**

- **More storage and duplicated data.** On my laptop the warehouse takes 970 MB, against 659 MB for the OLTP schema (about 47% more), even though it holds the same information. The bridges repeat the junction tables, the specialty is stored on every encounter, the summary table adds about 100 MB, and the fact table has several indexes.
- **A complicated ETL.** I now have a load script that has to be right: SCD Type 2 for providers, Unknown (-1) rows, removing duplicates, the readmission rule and late-arriving claims. A mistake there gives wrong numbers that still look believable. That's why the script checks row counts and money totals at the end. The full load took 8 min 35 s on my laptop.
- **Data is not live.** Reports only show data up to the last ETL run.
- **Less flexibility in some places.** The readmission rule is now fixed in the ETL. Changing it, for example to count any return visit instead of inpatient only, means reloading, not just editing a query. Storing `days_to_next_admission` helps a bit, because a 7-day or 60-day version can still be answered without a reload.

**What I gained:**

- Every query is faster, Q2 by about 136x with the summary table, and the gap should grow as the data grows. The OLTP self-join and row explosion get more expensive with every new row, while the stored values don't.
- The SQL is much simpler. Star Q3 is a count of a flag with one join, instead of a self-join with a date range and `COUNT(DISTINCT … FILTER …)`. Simpler queries are easier to get right.
- **History that OLTP can't give.** With SCD Type 2 on providers, old visits stay with the specialty the doctor had at that time, and `patient_age_at_encounter` doesn't change as patients get older.
- Reports no longer compete with the clinical system for the same database.

**Was it worth it?** Yes. PostgreSQL already handled the OLTP queries reasonably well at a million encounters (from under a second to 12 seconds), so just removing joins only gave 1.2x to 2.4x. The real value is in what the star schema allows me to store: the readmission flags, the pair counts, the billing totals and correct history. Those benefits grow with more data and more people running reports, while the ETL cost is a few minutes per night.

## Bridge tables: worth it?

I kept diagnoses and procedures in bridge tables because one visit can have many of each, with no fixed limit. Putting them in the fact table would mean either changing the grain, which would make every revenue `SUM` count the same money several times, or adding columns like `dx1` to `dx10`, which are awkward to query and limit the number of codes. Q2 needs every diagnosis × procedure pair on a visit, and only tables with one row per code can give that.

**The trade-off:** the bridges made Q2 about 3.5x faster (12.08 s → 3.41 s). They only hold integer keys and the ETL removed duplicate codes, so `COUNT(*)` replaces `COUNT(DISTINCT)`. I also added a shortcut to the query: a pair can't be more common than its rarer code, so codes too rare to reach the top 10 are skipped, which cuts the join from about 4.9 million pairs to about 670,000. But the bridges can't remove the row explosion itself, so Q2 is still the slowest star query. They also need care: if someone joins the fact table to a bridge and then sums the money, the revenue gets multiplied.

**In production** I would keep them, together with two things I already did: `primary_diagnosis_key` on the fact, because most reports only need the main diagnosis, and the `agg_dx_px_pair` summary table, rebuilt every night, because that's what made Q2 really fast (0.089 s). If revenue per diagnosis was ever needed, I would add a weight column (1 / diagnosis_count) to the diagnosis bridge.

## Performance quantification

**Example 1: Q3, 30-day readmission rate**

- Original execution time: **0.83 s**
- Optimized execution time: **0.21 s**
- Improvement: 0.83 / 0.21 = **about 3.9x faster**
- Main reason: pre-computation. The self-join on the encounters table runs once in the ETL and is stored as a TRUE/FALSE flag. The query only counts the flag over a partial index that holds the 150,393 inpatient stays, with a single join to `dim_specialty`.

**Example 2: Q2, top diagnosis-procedure pairs**

- Original execution time: **12.08 s**
- Optimized execution time: **3.41 s** with the bridge tables, **0.089 s** with the summary table
- Improvement: 12.08 / 3.41 = **about 3.5x faster** with bridges. 12.08 / 0.089 = **about 136x faster** with the summary table.
- Main reason: the bridges are narrow integer tables without duplicates, so `COUNT(*)` replaces a `COUNT(DISTINCT)` that sorted on disk, and the query skips codes too rare to reach the top 10. The summary table moves the whole pair count into the ETL, so the query just reads 10 rows from an index.

**Extra example: Q4, revenue by specialty and month**

- Original: **1.49 s**. Star, first version: 2.24 s. Star, rewritten: **1.20 s**.
- Improvement: **about 1.2x faster**
- Main reason: billing is already summed on the fact row and `specialty_key` is stored there, so the big join between billing and encounters is gone. It's the smallest gain because the OLTP query was already fairly cheap, and the fact table is much wider than billing. It's also the query that showed me how much the way you write a query matters.

**Takeaway:** the biggest improvements came from turning expensive logic into stored data: the readmission flag and the pair summary table. Putting the specialty and billing totals on the fact table gave a steady extra gain on top of that. Writing queries that group on integer keys before joining mattered as much as the schema itself.
