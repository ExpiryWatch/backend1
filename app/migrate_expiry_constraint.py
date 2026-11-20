
import sqlite3

db = sqlite3.connect("pantry.db")

try:
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("BEGIN IMMEDIATE")

    old_count = db.execute(
        "SELECT COUNT(*) FROM items"
    ).fetchone()[0]

    db.execute("""
        CREATE TABLE items_new (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            quantity NUMERIC(10, 2) NOT NULL,
            unit VARCHAR(16) DEFAULT 'шт' NOT NULL,
            category_id INTEGER,
            storage_location_id INTEGER,
            purchase_date DATE,
            expiry_date DATE,
            comment TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,

            CONSTRAINT ck_items_quantity_positive
                CHECK (quantity > 0),

            CONSTRAINT ck_items_name_not_blank
                CHECK (length(trim(name)) > 0),

            FOREIGN KEY(category_id)
                REFERENCES categories(id) ON DELETE RESTRICT,

            FOREIGN KEY(storage_location_id)
                REFERENCES storage_locations(id) ON DELETE RESTRICT
        )
    """)

    db.execute("INSERT INTO items_new SELECT * FROM items")
    db.execute("DROP TABLE items")
    db.execute("ALTER TABLE items_new RENAME TO items")

    for column in (
        "category_id",
        "name",
        "expiry_date",
        "storage_location_id",
    ):
        db.execute(
            f"CREATE INDEX ix_items_{column} ON items ({column})"
        )

    new_count = db.execute(
        "SELECT COUNT(*) FROM items"
    ).fetchone()[0]

    if new_count != old_count:
        raise RuntimeError("Количество продуктов изменилось!")

    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Обнаружены ошибки внешних ключей!")

    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("Ошибка целостности SQLite!")

    db.commit()

    print("Миграция выполнена успешно")
    print("Продуктов до:", old_count)
    print("Продуктов после:", new_count)
    print("Все 4 индекса восстановлены")

except Exception:
    db.rollback()
    raise

finally:
    db.close()
