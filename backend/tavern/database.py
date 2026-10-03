"""Per-session world snapshots for an App Platform PostgreSQL database."""

import json
from typing import Any, Mapping

import psycopg

from tavern.persistence import parse_world
from tavern.state import World


def load_database_world(url: str, session_id: str, slot: str) -> World | None:
    """Read a session's saved world, if one exists.

    Args:
        url: PostgreSQL connection URL.
        session_id: Device session that owns the snapshot.
        slot: Snapshot kind, such as the manual save or the autosave.
    Returns:
        Validated world or None when the session has nothing in this slot.
    Raises:
        psycopg.Error: The database cannot be read.
        ValueError: The saved world is invalid.
    """
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT snapshot::text FROM tavern_session WHERE session_id = %s AND slot = %s",
                           (session_id, slot))
            row = cursor.fetchone()
    return parse_world(row[0]) if row else None


def save_database_world(world: Mapping[str, Any], url: str, session_id: str, slot: str) -> None:
    """Atomically replace a session's saved world in PostgreSQL.

    Args:
        world: Serializable authoritative state.
        url: PostgreSQL connection URL.
        session_id: Device session that owns the snapshot.
        slot: Snapshot kind, such as the manual save or the autosave.
    Raises:
        psycopg.Error: The database cannot be written.
        ValueError: The world cannot be serialized.
    """
    encoded = json.dumps(world, allow_nan=False)
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tavern_session (session_id, slot, snapshot) VALUES (%s, %s, %s::jsonb) "
                           "ON CONFLICT (session_id, slot) DO UPDATE SET snapshot = EXCLUDED.snapshot",
                           (session_id, slot, encoded))


def initialize_database(url: str) -> None:
    """Create the session snapshot table if it does not exist.

    Args:
        url: PostgreSQL connection URL.
    Raises:
        psycopg.Error: The database cannot be initialized.
    """
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS tavern_session (session_id text NOT NULL, "
                           "slot text NOT NULL, snapshot jsonb NOT NULL, PRIMARY KEY (session_id, slot))")
