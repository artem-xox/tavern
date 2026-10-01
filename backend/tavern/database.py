"""One persistent world snapshot for an App Platform PostgreSQL database."""

import json
from typing import Any, Mapping

import psycopg

from tavern.persistence import parse_world


def load_database_world(url: str) -> dict[str, Any] | None:
    """Read the saved world, if one exists.

    Args:
        url: PostgreSQL connection URL.
    Returns:
        Validated world or None for a new database.
    Raises:
        psycopg.Error: The database cannot be read.
        ValueError: The saved world is invalid.
    """
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT snapshot::text FROM tavern_world WHERE id = 1")
            row = cursor.fetchone()
    return parse_world(row[0]) if row else None


def save_database_world(world: Mapping[str, Any], url: str) -> None:
    """Atomically replace the saved world in PostgreSQL.

    Args:
        world: Serializable authoritative state.
        url: PostgreSQL connection URL.
    Raises:
        psycopg.Error: The database cannot be written.
        ValueError: The world cannot be serialized.
    """
    encoded = json.dumps(world, allow_nan=False)
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tavern_world (id, snapshot) VALUES (1, %s::jsonb) "
                           "ON CONFLICT (id) DO UPDATE SET snapshot = EXCLUDED.snapshot", (encoded,))


def initialize_database(url: str) -> None:
    """Create the single-row world table if it does not exist.

    Args:
        url: PostgreSQL connection URL.
    Raises:
        psycopg.Error: The database cannot be initialized.
    """
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS tavern_world "
                           "(id integer PRIMARY KEY CHECK (id = 1), snapshot jsonb NOT NULL)")
