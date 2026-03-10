# Table Documentation Template

Use this template when generating table documentation at `docs/tables/<table_name>.md`.

Each doc has two parts: a **table summary** (row count, script link, key notes) followed by **column-by-column detail**.

Key Notes start blank and grow over time as confirmed knowledge about the table accumulates. Only verified facts belong here — unconfirmed observations or hypotheses belong in data validation, not here.

Each column's stats section uses one of the following formats:

- **Categorical (unique)** — all values are unique or unique except nulls. Shows distinct count, "Unique" label, null count.
- **Categorical (few)** — 10 or fewer distinct values. Lists all values with counts.
- **Categorical (many)** — more than 10 distinct values. Shows distinct count, top 3 values with counts, null count.
- **Numeric** — always the same format. Shows min, max, avg, null count.
- **Date (short range)** — range under 15 months. Shows min/max excluding special years (1900/9999), count by month, missing months.
- **Date (long range)** — range 15 months or more. Shows min/max excluding special years, count by year, missing months.

## Example

```markdown
# l10wrk_sales

- **Row count**: 45,230
- **Ingestion script**: [l10wrk_sales.py](../../analysis/l10wrk_sales.py)

## Key Notes

- Each row represents a single transaction line item
- Revenue is net of GST

## Columns

### customer_id (INTEGER) — Categorical
- 12,408 distinct values
- Unique (no duplicates)
- Nulls: 0

### region (VARCHAR) — Categorical
- 5 distinct values: NSW (12,300), VIC (10,200), QLD (8,900), WA (7,400), SA (6,430)
- Nulls: 0

### product_name (VARCHAR) — Categorical
- 847 distinct values
- Top 3: Widget Pro (2,340), Widget Basic (1,890), Gadget X (1,450)
- Nulls: 12

### revenue (DOUBLE) — Numeric
- Min: -450.00 | Max: 149,230.00 | Avg: 2,340.12
- Nulls: 23

### order_date (DATE) — Date
- Range: 2021-03-15 to 2025-11-30
- Nulls: 0 | Special dates (1900/9999): 12
- Count by year: 2021 (8,200), 2022 (10,100), 2023 (9,800), 2024 (11,300), 2025 (5,830)
- Missing months: 2023-06, 2023-07

### signup_date (DATE) — Date
- Range: 2025-01-05 to 2025-09-28
- Nulls: 4 | Special dates (1900/9999): 0
- Count by month: 2025-01 (120), 2025-02 (135), 2025-03 (142), 2025-04 (98), 2025-05 (110), 2025-06 (88), 2025-07 (156), 2025-08 (130), 2025-09 (71)
```
