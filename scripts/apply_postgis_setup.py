from pathlib import Path
import os

import asyncpg


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    sql_path = (
        Path(__file__).resolve().parent.parent / "migrations" / "models" / "0001_postgis_setup.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")

    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(sql)
    finally:
        await connection.close()

    print("Applied PostGIS setup SQL")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
