-- AUTOMATION TRIGGERS

-- TRIGGER 1: Auto-Deduct Stock & Log Inventory
-- When a new order item is added, reduce the product stock and write a negative entry into the inventory log.

CREATE OR REPLACE FUNCTION fn_deduct_stock()
RETURNS TRIGGER AS $$
BEGIN
    -- 1. Deduct stock
    UPDATE products 
    SET stock_qty = stock_qty - NEW.quantity 
    WHERE product_id = NEW.product_id;

    -- 2. Write to inventory log
    INSERT INTO inventory_logs (product_id, change_qty, change_type, reference_id) 
    VALUES (NEW.product_id, -NEW.quantity, 'ORDER', NEW.order_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_deduct_stock
AFTER INSERT ON order_details
FOR EACH ROW
EXECUTE FUNCTION fn_deduct_stock();


-- TRIGGER 2: Auto-Update Customer Tier
-- When a customer's total_spent is updated, automatically upgrade or downgrade their tier based on the new amount.

CREATE OR REPLACE FUNCTION fn_update_customer_tier()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_spent >= 1000 THEN 
        NEW.tier := 'Gold';
    ELSIF NEW.total_spent >= 500 THEN 
        NEW.tier := 'Silver';
    ELSE 
        NEW.tier := 'Bronze';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customer_tier
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION fn_update_customer_tier();

-- TRIGGER 3: Auto-Log Restocking
-- When a product's stock increases (replenishment),automatically write a positive entry to the inventory log.

CREATE OR REPLACE FUNCTION fn_log_restock()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.stock_qty > OLD.stock_qty THEN
        INSERT INTO inventory_logs (product_id, change_qty, change_type)
        VALUES (NEW.product_id, NEW.stock_qty - OLD.stock_qty, 'REPLENISHMENT');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_restock
AFTER UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION fn_log_restock();