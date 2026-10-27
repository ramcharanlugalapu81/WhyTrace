"""Deterministic, small retail dataset with one planted cause and one decoy."""
from __future__ import annotations

import duckdb
import random


def create_sample_database(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE store (s_store_sk INTEGER, s_store_id VARCHAR, s_store_name VARCHAR);
        INSERT INTO store VALUES (1,'S1','North Shop'),(2,'S2','Central Shop'),(3,'S3','South Shop');
        CREATE TABLE item (i_item_sk INTEGER, i_item_id VARCHAR, i_category VARCHAR);
        INSERT INTO item VALUES (1,'I1','Home'),(2,'I2','Electronics'),(3,'I3','Apparel');
        CREATE TABLE date_dim (d_date_sk INTEGER, d_date DATE, d_year INTEGER, d_moy INTEGER);
        CREATE TABLE store_sales (ss_ticket_number INTEGER, ss_sold_date_sk INTEGER, ss_store_sk INTEGER, ss_item_sk INTEGER, ss_quantity INTEGER, ss_net_paid DECIMAL(12,2));
        CREATE TABLE store_returns (sr_returned_date_sk INTEGER, sr_store_sk INTEGER, sr_item_sk INTEGER, sr_return_quantity INTEGER, sr_return_amt DECIMAL(12,2));
        CREATE TABLE inventory (inv_date_sk INTEGER, inv_store_sk INTEGER, inv_item_sk INTEGER, inv_quantity_on_hand INTEGER);
    """)
    con.execute("""
      INSERT INTO date_dim
      SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, year(d), month(d)
      FROM generate_series(DATE '2026-01-01', DATE '2026-04-30', INTERVAL 1 DAY) t(d);
    """)
    # Seeded day-to-day variation keeps the sample realistic and reproducible.
    rng = random.Random(2026)
    dates = con.execute("SELECT d_date_sk,d_year,d_moy FROM date_dim WHERE d_date < DATE '2026-04-01' ORDER BY d_date").fetchall()
    sales = []
    ticket = 0
    for date_sk, year, month in dates:
        for store_sk, store_id in ((1, "S1"), (2, "S2"), (3, "S3")):
            for item_sk in (1, 2, 3):
                ticket += 1
                baseline = 50 if store_id == "S3" and year == 2026 and month == 3 else 100
                sales.append((ticket, date_sk, store_sk, item_sk, 1, baseline + rng.randint(-5, 5)))
    con.executemany("INSERT INTO store_sales VALUES (?,?,?,?,?,?)", sales)
    # Returns are normally small; Electronics has a March-only spike that remains
    # far too small to account for the planted store revenue drop.
    con.execute("""
      INSERT INTO store_returns
      SELECT dd.d_date_sk, st.s_store_sk, it.i_item_sk,
             CASE WHEN dd.d_moy=3 AND it.i_category='Electronics' THEN 2 ELSE 1 END,
             CAST(CASE WHEN dd.d_moy=3 AND it.i_category='Electronics' THEN 8 ELSE 2 END AS DECIMAL(12,2))
      FROM date_dim dd CROSS JOIN store st CROSS JOIN item it
      WHERE dd.d_date < DATE '2026-04-01'
    """)
    con.execute("""
      INSERT INTO inventory
      SELECT dd.d_date_sk, st.s_store_sk, it.i_item_sk,
             100
      FROM date_dim dd CROSS JOIN store st CROSS JOIN item it
      WHERE dd.d_date < DATE '2026-04-01'
    """)
    return con


def get_connection() -> duckdb.DuckDBPyConnection:
    return create_sample_database()
