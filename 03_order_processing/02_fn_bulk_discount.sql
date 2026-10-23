 -- Function bulk discount

-- Calculates the discount % based on the quantity bought.
-- 50+ items = 20% off
-- 10+ items = 10% off
-- Under 10 = 0% off

CREATE OR REPLACE FUNCTION fn_bulk_discount(p_quantity INT)
RETURNS NUMERIC(5,2)
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_quantity >= 50 THEN 20.00
        WHEN p_quantity >= 10 THEN 10.00
        ELSE 0.00
    END;
$$;