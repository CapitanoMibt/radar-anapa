
import os
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]


def init_db():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'Черновик',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200),
                    content TEXT,
                    status VARCHAR(50) DEFAULT 'Получено',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS source_name VARCHAR(200)
            """)

            cur.execute("""
                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS source_url TEXT
            """)

            cur.execute("""
                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64)
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                messages_fingerprint_unique
                ON messages (fingerprint)
                WHERE fingerprint IS NOT NULL
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    url TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'Не подключён',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(200) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
