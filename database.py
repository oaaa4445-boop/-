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
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        try:
            await conn.execute("ALTER TABLE users ALTER COLUMN user_id TYPE BIGINT")
            print("✅ Тип user_id изменён на BIGINT")
        except Exception as e:
            print(f"⚠️ Не удалось изменить тип user_id: {e}")
        
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except:
            pass
        
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
        rows = await conn.fetch("SELECT * FROM categories ORDER BY id")
        return [{"id": r['id'], "name": r['name'], "image": r['image']} for r in rows]
    finally:
        await conn.close()

async def get_category_by_id(cat_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM categories WHERE id=$1", cat_id)
        if row:
            return {"id": row['id'], "name": row['name'], "image": row['image']}
        return None
    finally:
        await conn.close()

async def get_category_by_name(name):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM categories WHERE name=$1", name)
        if row:
            return {"id": row['id'], "name": row['name'], "image": row['image']}
        return None
    finally:
        await conn.close()

async def add_category(name, image_url):
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
    """Удаляет категорию. Возвращает (успех, количество товаров в категории)."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT name FROM categories WHERE id=$1", category_id)
        if not row:
            return False, 0
        category_name = row['name']
        
        # Проверяем, есть ли товары в этой категории
        count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE category=$1", category_name)
        if count > 0:
            return False, count  # Нельзя удалить — есть товары
        
        await conn.execute("DELETE FROM categories WHERE id=$1", category_id)
        return True, 0
    finally:
        await conn.close()

async def get_products(category):
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT * FROM products WHERE category=$1 ORDER BY id DESC", category)
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

async def search_products(query):
    if not query or len(query.strip()) < 2:
        return []
    conn = await get_db()
    try:
        search_pattern = f"%{query.lower()}%"
        rows = await conn.fetch(
            "SELECT * FROM products WHERE LOWER(name) LIKE $1 OR LOWER(description) LIKE $1",
            search_pattern
        )
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
        username = username if username else ""
        full_name = full_name if full_name else ""
        await conn.execute(
            """INSERT INTO users (user_id, username, full_name) 
               VALUES ($1::bigint, $2, $3) 
               ON CONFLICT (user_id) 
               DO UPDATE SET username = $2, full_name = $3""",
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
