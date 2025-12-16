from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

# Global model instance (loaded once, reused)
_model = None

def get_embedding_model():
    """
    Get or initialize the embedding model (singleton pattern).
    Model is loaded once and reused for efficiency.

    Returns:
        SentenceTransformer model
    """
    global _model
    if _model is None:
        print("Loading embedding model: all-MiniLM-L6-v2...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Model loaded!")
    return _model


def create_embedding(text: str) -> List[float]:
    """
    Create embedding for a single text using local Sentence Transformer model.

    Args:
        text: Text to embed

    Returns:
        Embedding vector (384 dimensions)
    """
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


def create_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Create embeddings for multiple texts in batches.
    More efficient than calling create_embedding() multiple times.

    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process at once (default: 32)

    Returns:
        List of embedding vectors
    """
    model = get_embedding_model()

    # Process in batches for memory efficiency
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(embeddings.tolist())

    return all_embeddings


def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Similarity score (0-1, where 1 is identical)
    """
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)

    # Cosine similarity formula
    similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    return float(similarity)
