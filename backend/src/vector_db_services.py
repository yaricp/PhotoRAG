from loguru import logger
from sqlalchemy import text
from typing import List, Optional, Tuple
import numpy as np

from src.models import PhotoEmbedding


# ----------------------------
# Save embedding
# ----------------------------
def save_embedding(db, photo_embedding_id: int, embedding: List[float]) -> int:
    """
    Saves embedding to the vector DB and return the rowid.
    """
    try:
        embedding_bytes = np.array(embedding, dtype=np.float32).flatten().tobytes()

        db.execute(text("""
            INSERT INTO photo_embeddings_vss(rowid, embedding)
            VALUES (:id, :embedding)
        """), {"id": photo_embedding_id, "embedding": embedding_bytes})

        db.commit()

        logger.info(f"Embedding saved, rowid={photo_embedding_id}")
        return photo_embedding_id

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving embedding: {e}")
        raise


# ----------------------------
# Link photo ↔ embedding
# ----------------------------
def link_photo_embedding(
    db, photo_id: int, model: str
):
    """
    Stores mapping between photo and vector row.
    """
    try:
        db.execute(text(
            """
            INSERT INTO photo_embedding_map(photo_id, model)
            VALUES (:photo_id, :model)
            """),
            {"photo_id": photo_id, "model": model}
        )
        photo_embedding = PhotoEmbedding(photo_id=photo_id, model=model)
        db.add(photo_embedding)
        db.commit()
        db.refresh(photo_embedding)
        logger.info(f"Linked photo_id={photo_id} → embedding_id={photo_embedding.id}")
        return photo_embedding.id

    except Exception as e:
        db.rollback()
        logger.error(f"Error linking photo embedding: {e}")
        raise


# ----------------------------
# Full pipeline save
# ----------------------------
def store_photo_embedding(
    db, photo_id: int, embedding: List[float], model: str
) -> int:
    """
    One-step helper: save embedding + link to photo.
    """
    photo_embedding_id = link_photo_embedding(db, photo_id, model)
    rowid = save_embedding(db, photo_embedding_id, embedding)
    
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
        embedding_bytes = np.array(query_embedding, dtype=np.float32).flatten().tobytes()

        rows = db.execute(text("""
            SELECT m.photo_id, v.distance
            FROM photo_embeddings_vss v
            JOIN photo_embedding_map m ON v.rowid = m.id
            WHERE v.embedding MATCH :embedding AND v.distance < 0.89
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
def get_embedding_by_photo(db, photo_id: int) -> Optional[List[float]]:
    """
    Debug only — usually not needed in vector DB systems.
    """
    try:
        row = db.execute(
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