import asyncpg
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT,
                image TEXT
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                category TEXT,
                name TEXT,
                description TEXT,
                price REAL,
                image TEXT,
                flavors TEXT
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        existing = await conn.fetch("SELECT COUNT(*) FROM categories")
        if existing[0]['count'] == 0:
            await conn.executemany(
                "INSERT INTO categories (id, name, image) VALUES ($1, $2, $3)",
                [
                    (1, 'Одноразки', ''),
                    (2, 'Под-системы', ''),
                    (3, 'Жидкость', ''),
                    (4, 'Расходники', ''),
                    (5, 'Жевательный табак', ''),
                    (6, 'Кальяны', ''),
                ]
            )
        
        print("✅ База данных PostgreSQL готова")
    finally:
        await conn.close()

async def get_categories():
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT * FROM categories")
        return [{"id": r['id'], "name": r['name'], "image": r['image']} for r in rows]
    finally:
        await conn.close()

async def get_all_categories():
    return await get_categories()

async def add_category(name, image_url):
    """Добавить новую категорию с фото"""
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT MAX(id) as max_id FROM categories")
        new_id = (row['max_id'] or 0) + 1
        await conn.execute(
            "INSERT INTO categories (id, name, image) VALUES ($1, $2, $3)",
            new_id, name, image_url
        )
        return new_id
    finally:
        await conn.close()

async def delete_category(category_id):
    """Удалить категорию. Возвращает (success, products_count)"""
    conn = await get_db()
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE category = (SELECT name FROM categories WHERE id=$1)", category_id)
        if count > 0:
            return False, count
        await conn.execute("DELETE FROM categories WHERE id=$1", category_id)
        return True, 0
    finally:
        await conn.close()

async def get_products(category):
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT * FROM products WHERE category=$1", category)
        return [{
            "id": r['id'], "category": r['category'], "name": r['name'],
            "description": r['description'], "price": r['price'],
            "image": r['image'], "flavors": r['flavors']
        } for r in rows]
    finally:
        await conn.close()

async def get_products_by_ids(ids):
    if not ids:
        return []
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT * FROM products WHERE id = ANY($1::int[])", list(ids))
        return [{
            "id": r['id'], "category": r['category'], "name": r['name'],
            "description": r['description'], "price": r['price'],
            "image": r['image'], "flavors": r['flavors']
        } for r in rows]
    finally:
        await conn.close()

async def add_product(category, name, description, price, image, flavors):
    conn = await get_db()
    try:
        result = await conn.fetchrow(
            "INSERT INTO products (category, name, description, price, image, flavors) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            category, name, description, price, image, flavors
        )
        return result['id']
    finally:
        await conn.close()

async def delete_product(product_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT image FROM products WHERE id=$1", product_id)
        await conn.execute("DELETE FROM products WHERE id=$1", product_id)
        return row['image'] if row else None
    finally:
        await conn.close()

async def save_user(user_id, username, full_name):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING",
            user_id, username, full_name
        )
    finally:
        await conn.close()

async def get_all_users():
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r['user_id'] for r in rows]
    finally:
        await conn.close()

async def get_product_count():
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT COUNT(*) FROM products")
        return row['count']
    finally:
        await conn.close()

async def get_user_count():
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        return row['count']
    finally:
        await conn.close()
