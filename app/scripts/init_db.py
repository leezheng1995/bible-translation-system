from app.core.database import DATABASE_URL, get_table_names, init_db


def main() -> None:
    print("Initializing SQLite database...")
    print(f"DATABASE_URL={DATABASE_URL}")

    init_db()

    tables = get_table_names()

    print("Database initialized successfully.")
    print(f"Total tables: {len(tables)}")
    for table in tables:
        print(f"- {table}")


if __name__ == "__main__":
    main()
