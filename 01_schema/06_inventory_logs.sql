-- Create inventory_logs table


DROP TABLE IF EXISTS inventory_logs CASCADE;

CREATE TABLE inventory_logs (
    log_id        BIGSERIAL    PRIMARY KEY,
    product_id    INT          NOT NULL
                  REFERENCES products (product_id) ON DELETE RESTRICT,
    change_qty    INT          NOT NULL,          -- negative = out, positive = in
    change_type   VARCHAR(20)  NOT NULL,          -- INITIAL / ORDER / ORDER_CANCELLED / REPLENISHMENT / ADJUSTMENT
    previous_qty  INT          NOT NULL,
    new_qty       INT          NOT NULL,
    reference_id  INT,                            -- order_id for ORDER / ORDER_CANCELLED rows
    note          VARCHAR(255),
    changed_by    VARCHAR(100) NOT NULL DEFAULT CURRENT_USER,
    changed_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
