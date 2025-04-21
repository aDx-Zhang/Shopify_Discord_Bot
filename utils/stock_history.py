
import sqlite3
from datetime import datetime

class StockHistory:
    def __init__(self, db_path):
        self.db_path = db_path
        
    def log_stock_change(self, product_url, quantity):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO stock_history (product_url, quantity, timestamp)
                VALUES (?, ?, ?)
            """, (product_url, quantity, datetime.now()))
