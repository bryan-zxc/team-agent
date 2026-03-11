# Analysis Table Documentation Template

Use this template when generating table documentation at `docs/tables/<table_name>.md` for derived (l20drv) and export (l30exp) tables.

Each doc has a **table summary** (row count, primary key, unique constraints, script link, key notes).

Key Notes start blank and grow over time as confirmed knowledge about the table accumulates. Only verified facts belong here — unconfirmed observations or hypotheses belong in data validation, not here.

## Example 1: natural primary key

```markdown
# l20drv_sales_by_region

- **Row count**: 1,200
- **Primary key**: region, quarter
- **SQL script**: [l20drv_sales_by_region.sql](../../analysis/l20drv_sales_by_region.sql)

## Key Notes

- Quarters with fewer than 10 transactions are excluded
- Derived from l10wrk_sales
```

## Example 2: surrogate key with unique constraint

```markdown
# l20drv_customers

- **Row count**: 12,408
- **Primary key**: customer_sk
- **Unique constraint**: source_system, customer_id
- **SQL script**: [l20drv_customers.sql](../../analysis/l20drv_customers.sql)

## Key Notes

- Merges customers from l10wrk_customers_au and l10wrk_customers_nz
```
