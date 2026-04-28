from loguru import logger
from sqlalchemy import text
from typing import List, Optional, Tuple
import numpy as np


# ----------------------------
# Save embedding
# ----------------------------
def save_embedding(db_session, photo_id: int, embedding: List[float]) -> int:
    try:
        # list[float] → bytes (little-endian 32-bit floats)
        embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

        db_session.execute(text("""
            INSERT INTO photo_embeddings_vss(rowid, embedding)
            VALUES (:id, :embedding)
        """), {"id": photo_id, "embedding": embedding_bytes})

        db_session.commit()

        rowid = db_session.execute(text("SELECT last_insert_rowid()")).scalar()
        
        logger.info(f"Embedding saved, rowid={rowid}")
        return rowid

    except Exception as e:
        db_session.rollback()
        logger.error(f"Error saving embedding: {e}")
        raise


# ----------------------------
# Link photo ↔ embedding
# ----------------------------
def link_photo_embedding(db_session, photo_id: int, rowid: int, model: str):
    """
    Stores mapping between photo and vector row.
    """
    try:
        db_session.execute(text(
            """
            INSERT INTO photo_embedding_map(photo_id, vss_rowid, model)
            VALUES (:photo_id, :rowid, :model)
            """),
            {"photo_id": photo_id, "rowid": rowid, "model": model}
        )

        db_session.commit()
        logger.info(f"Linked photo_id={photo_id} → rowid={rowid}")

    except Exception as e:
        db_session.rollback()
        logger.error(f"Error linking photo embedding: {e}")
        raise


# ----------------------------
# Full pipeline save
# ----------------------------
def store_photo_embedding(
    db_session, photo_id: int, embedding: List[float], model: str
) -> int:
    """
    One-step helper: save embedding + link to photo.
    """
    rowid = save_embedding(db_session, photo_id, embedding)
    link_photo_embedding(db_session, photo_id, rowid, model)
    return rowid


# ----------------------------
# Search similar photos
# ----------------------------
def search_similar_photos(
    db,
    query_embedding: List[float],
    limit: int = 10
) -> List[Tuple[int, float]]:
    try:
        embedding_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

        rows = db.execute(text("""
            SELECT m.photo_id, v.distance
            FROM photo_embeddings_vss v
            JOIN photo_embedding_map m ON v.rowid = m.vss_rowid
            WHERE v.embedding MATCH :embedding
            AND v.k = :k
            ORDER BY v.distance
        """), {"embedding": embedding_bytes, "k": limit}).fetchall()

        logger.info(f"Vector search returned {len(rows)} results")

        return [(r[0], r[1]) for r in rows]

    except Exception as e:
        logger.error(f"Error searching embeddings: {e}")
        return []


# ----------------------------
# Optional: debug helper
# ----------------------------
def get_embedding_by_photo(db_session, photo_id: int) -> Optional[List[float]]:
    """
    Debug only — usually not needed in vector DB systems.
    """
    try:
        row = db_session.execute(
            """
            SELECT v.embedding
            FROM photo_embeddings_vss v
            JOIN photo_embedding_map m ON v.rowid = m.rowid
            WHERE m.photo_id = ?
            """,
            (photo_id,)
        ).fetchone()

        if not row:
            return None

        return row[0]

    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return None