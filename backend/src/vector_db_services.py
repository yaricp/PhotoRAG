from loguru import logger
from sqlalchemy import text
from typing import List, Optional, Tuple
import numpy as np

from src.models import PhotoEmbedding
from src.config import Embedding_Settings as ML_Settings


# ---------------------------------------------------------------------------
# Dimension helpers
# ---------------------------------------------------------------------------

_DIMENSION_MAP = {
    # OpenAI
    "text-embedding-3-large":       3072,
    "text-embedding-3-small":       1536,
    "text-embedding-ada-002":       1536,
    # Google
    "text-embedding-004":           768,
    "text-multilingual-embedding":  768,
    # Nomic
    "nomic-embed-text":             768,
    "nomic":                        768,
    # BAAI / FlagEmbedding
    "bge-large":                    1024,
    "bge-base":                     768,
    "bge-small":                    512,
    "bge-m3":                       1024,
    # sentence-transformers common
    "all-mpnet-base":               768,
    "all-minilm-l12":               384,
    "all-minilm-l6":                384,
    "paraphrase-minilm":            384,
    "multilingual-e5-large":        1024,
    "multilingual-e5-base":         768,
    "multilingual-e5-small":        384,
    "e5-large":                     1024,
    "e5-base":                      768,
    "e5-small":                     384,
    "gte-large":                    1024,
    "gte-base":                     768,
}

def get_embedding_dimension(model_name: str) -> int:
    """Return the output dimension for a known embedding model, defaulting to 768."""
    lower = model_name.lower()
    for key, dim in _DIMENSION_MAP.items():
        if key in lower:
            return dim
    return 768


def current_vss_dimension(db) -> int:
    """Read the dimension that the photo_embeddings_vss table was created with."""
    row = db.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='photo_embeddings_vss'"
    )).fetchone()
    if row and row[0]:
        import re
        m = re.search(r"FLOAT\[(\d+)\]", row[0], re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 768


def rebuild_embeddings_vss(db, new_dimension: int) -> None:
    """
    Drop and recreate photo_embeddings_vss with a new dimension.
    Also clears photo_embedding_map so photos will be re-embedded.
    """
    logger.info(f"[vector_db] Rebuilding photo_embeddings_vss with dim={new_dimension}")
    with db.bind.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS photo_embeddings_vss"))
        conn.execute(text(f"""
            CREATE VIRTUAL TABLE photo_embeddings_vss
            USING vec0(embedding FLOAT[{new_dimension}])
        """))
    db.execute(text("DELETE FROM photo_embedding_map"))
    db.commit()
    logger.info(f"[vector_db] Rebuild complete — photo_embedding_map cleared, re-embedding needed")


# ----------------------------
# Save embedding
# ----------------------------
def save_embedding(db, photo_embedding_id: int, embedding: List[float]) -> int:
    """
    Saves embedding to the vector DB and returns the rowid.
    Auto-rebuilds the VSS table if the dimension doesn't match the vector.
    """
    embedding_bytes = np.array(embedding, dtype=np.float32).flatten().tobytes()

    try:
        db.execute(text("""
            INSERT INTO photo_embeddings_vss(rowid, embedding)
            VALUES (:id, :embedding)
        """), {"id": photo_embedding_id, "embedding": embedding_bytes})
        db.commit()
        logger.info(f"Embedding saved, rowid={photo_embedding_id}")
        return photo_embedding_id

    except Exception as e:
        db.rollback()
        if "Dimension mismatch" in str(e):
            new_dim = len(embedding)
            logger.warning(
                f"[vector_db] Dimension mismatch — rebuilding VSS table with dim={new_dim} and retrying"
            )
            rebuild_embeddings_vss(db, new_dim)
            # Retry once with the freshly recreated table
            db.execute(text("""
                INSERT INTO photo_embeddings_vss(rowid, embedding)
                VALUES (:id, :embedding)
            """), {"id": photo_embedding_id, "embedding": embedding_bytes})
            db.commit()
            logger.info(f"Embedding saved after rebuild, rowid={photo_embedding_id}")
            return photo_embedding_id
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

def _scaled_threshold(base: float, dim: int) -> float:
    """Scale the L2 distance threshold for the embedding dimension in use.
    Uses square-root scaling: threshold grows proportionally to the 'radius'
    of the embedding space, which scales as sqrt(dim)."""
    return base * (dim / 768) ** 0.5


def search_similar_photos(
    db,
    query_embedding: List[float],
    limit: int = 10,
    similarity_limit: Optional[float] = None,
) -> List[Tuple[int, float]]:
    try:
        embedding_bytes = np.array(query_embedding, dtype=np.float32).flatten().tobytes()
        if similarity_limit is not None:
            threshold = similarity_limit
        else:
            base = ML_Settings().EMBEDDING_SIMILARITY_LIMIT
            threshold = _scaled_threshold(base, len(query_embedding))
        logger.debug(f"Vector search: dim={len(query_embedding)} threshold={threshold:.3f}")

        # Run KNN in a subquery first, then JOIN — avoids sqlite-vec optimizer issues
        # with JOIN + MATCH in the same query level.
        rows = db.execute(text("""
            SELECT m.photo_id, knn.distance
            FROM (
                SELECT rowid, distance
                FROM photo_embeddings_vss
                WHERE embedding MATCH :embedding AND k = :k
                ORDER BY distance
            ) knn
            JOIN photo_embedding_map m ON knn.rowid = m.id
            WHERE knn.distance < :threshold
        """), {"embedding": embedding_bytes, "k": limit, "threshold": threshold}).fetchall()

        logger.info(f"Vector search returned {len(rows)} results (threshold={threshold:.3f})")

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