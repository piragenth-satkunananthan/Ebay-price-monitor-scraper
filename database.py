import sqlite3
import pandas as pd

conn = sqlite3.connect("ebay_scraper.db", check_same_thread=False)
cursor = conn.cursor()

# Create Products Table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        url TEXT UNIQUE,
        image_link TEXT
    )
''')

# Create Price History Table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        price REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
''')
conn.commit()


def add_new_product(title, url, image_link):
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO products (title, url, image_link) VALUES (?, ?, ?)',
            (title, url, image_link)
        )
        conn.commit()
        return True
    except Exception:
        return False


def add_new_price_history(url, price):
    try:
        cursor.execute('SELECT id FROM products WHERE url = ?', (url,))
        row = cursor.fetchone()
        if row is None:
            return False  # FIX: guard against url not found
        product_id = row[0]
        cursor.execute(
            'INSERT INTO price_history (product_id, price) VALUES (?, ?)',
            (product_id, price)
        )
        conn.commit()
        return True
    except Exception:
        return False


def get_monitored_products():
    """Fetches all products and their latest price."""
    query = '''
        SELECT
            p.id,
            p.title,
            p.url        AS link,
            p.image_link,
            ph.price
        FROM products p
        LEFT JOIN price_history ph ON ph.id = (
            SELECT id FROM price_history
            WHERE product_id = p.id
            ORDER BY timestamp DESC
            LIMIT 1
        )
    '''
    return pd.read_sql(query, conn)


def get_product_price_history(product_id):
    """Fetches the full price timeline for a specific product."""
    query = '''
        SELECT timestamp AS date, price
        FROM price_history
        WHERE product_id = ?
        ORDER BY timestamp ASC
    '''
    # FIX: lowercase column names ('date', 'price') to match main.py references
    df = pd.read_sql(query, conn, params=(product_id,))

    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])

    return df  # FIX: do NOT set_index — main.py needs 'date' as a plain column for Plotly


def delete_product(product_id):
    cursor.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    # FIX: removed conn.close() — closing here would break all future DB calls