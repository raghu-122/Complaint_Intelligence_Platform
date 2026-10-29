"""
Migration: Add order_items table and product_id_fk to complaints.
Run once against the existing database to apply schema changes.
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "complaint_intelligence.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Create order_items table if it does not exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_item_id VARCHAR(30) NOT NULL UNIQUE,
        order_id_fk INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id_fk INTEGER NOT NULL REFERENCES products(id),
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price NUMERIC(10, 2) NOT NULL,
        discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
        line_total NUMERIC(10, 2) NOT NULL,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_order_item_quantity_positive CHECK (quantity > 0),
        CONSTRAINT ck_order_item_unit_price_non_negative CHECK (unit_price >= 0),
        CONSTRAINT ck_order_item_line_total_non_negative CHECK (line_total >= 0)
    )
    """)
    print("[OK] order_items table ready")

    # 2. Add product_id_fk to complaints if missing
    cur.execute("PRAGMA table_info(complaints)")
    cols = {row[1] for row in cur.fetchall()}
    if "product_id_fk" not in cols:
        cur.execute("ALTER TABLE complaints ADD COLUMN product_id_fk INTEGER REFERENCES products(id)")
        print("[OK] complaints.product_id_fk column added")
    else:
        print("[SKIP] complaints.product_id_fk already present")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
