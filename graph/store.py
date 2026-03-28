import json
import pathlib
import aiosqlite

from graph.models import Node

DB_PATH = "regflow.db"
SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "db" / "schema.sql"


async def _get_db_path(db_path: str | None = None) -> str:
    return db_path or DB_PATH


async def init_db(db_path: str | None = None) -> None:
    db_path = await _get_db_path(db_path)
    sql = SCHEMA_PATH.read_text()
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(sql)
        await db.commit()


async def upsert_node(node: Node, db_path: str | None = None) -> None:
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO nodes (url, parent_url, extraction_goal, depth_from_seed,
                               section_type, relevant_form_fields, content_hash,
                               last_extracted_json, last_extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                parent_url = excluded.parent_url,
                extraction_goal = excluded.extraction_goal,
                depth_from_seed = excluded.depth_from_seed,
                section_type = excluded.section_type,
                relevant_form_fields = excluded.relevant_form_fields,
                content_hash = excluded.content_hash,
                last_extracted_json = excluded.last_extracted_json,
                last_extracted_at = excluded.last_extracted_at
            """,
            (
                node.url,
                node.parent_url,
                node.extraction_goal,
                node.depth_from_seed,
                node.section_type,
                node.relevant_form_fields,
                node.content_hash,
                node.last_extracted_json,
                node.last_extracted_at,
            ),
        )
        await db.commit()


def _row_to_node(row: aiosqlite.Row) -> Node:
    return Node(
        id=row["id"],
        url=row["url"],
        parent_url=row["parent_url"],
        extraction_goal=row["extraction_goal"],
        depth_from_seed=row["depth_from_seed"],
        section_type=row["section_type"],
        relevant_form_fields=row["relevant_form_fields"],
        content_hash=row["content_hash"],
        last_extracted_json=row["last_extracted_json"],
        last_extracted_at=row["last_extracted_at"],
        created_at=row["created_at"],
    )


async def get_node(url: str, db_path: str | None = None) -> Node | None:
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM nodes WHERE url = ?", (url,)) as cursor:
            row = await cursor.fetchone()
            return _row_to_node(row) if row else None


async def get_nodes_by_form_fields(fields: list[str], db_path: str | None = None) -> list[Node]:
    db_path = await _get_db_path(db_path)
    target = set(fields)
    results = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM nodes WHERE relevant_form_fields IS NOT NULL") as cursor:
            async for row in cursor:
                try:
                    node_fields = set(json.loads(row["relevant_form_fields"]))
                    if node_fields & target:
                        results.append(_row_to_node(row))
                except (json.JSONDecodeError, TypeError):
                    continue
    return results


async def save_version(node_id: int, hash: str, json_str: str, db_path: str | None = None) -> None:
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO node_versions (node_id, content_hash, extracted_json) VALUES (?, ?, ?)",
            (node_id, hash, json_str),
        )
        await db.commit()


async def update_node_url(old_url: str, new_url: str, db_path: str | None = None) -> bool:
    """Update a node's URL in place, preserving row ID and version history.

    Returns True on success, False if old_url not found or new_url conflicts.
    """
    db_path = await _get_db_path(db_path)
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "UPDATE nodes SET url = ? WHERE url = ?",
                (new_url, old_url),
            )
            await db.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


async def get_prior_version(node_id: int, db_path: str | None = None) -> str | None:
    """Get the second-most-recent extracted_json from node_versions.

    Returns None if fewer than 2 versions exist.
    """
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT extracted_json FROM node_versions WHERE node_id = ? ORDER BY id DESC LIMIT 1 OFFSET 1",
            (node_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_meta(key: str, db_path: str | None = None) -> str | None:
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT value FROM graph_meta WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_meta(key: str, value: str, db_path: str | None = None) -> None:
    db_path = await _get_db_path(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO graph_meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value),
        )
        await db.commit()
