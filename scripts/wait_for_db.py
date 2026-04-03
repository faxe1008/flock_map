import asyncio
import os

import asyncpg


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    max_attempts = int(os.environ.get("DB_WAIT_MAX_ATTEMPTS", "60"))
    sleep_seconds = float(os.environ.get("DB_WAIT_SLEEP_SECONDS", "2"))

    for attempt in range(1, max_attempts + 1):
        try:
            connection = await asyncpg.connect(database_url)
            await connection.close()
            print(f"Database is ready after {attempt} attempt(s)")
            return
        except Exception as error:
            print(f"Waiting for database ({attempt}/{max_attempts}): {error}")
            await asyncio.sleep(sleep_seconds)

    raise RuntimeError("Database did not become ready in time")


if __name__ == "__main__":
    asyncio.run(main())
