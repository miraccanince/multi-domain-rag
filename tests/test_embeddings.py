"""
Unit tests for embedding module.
"""
import pytest
import numpy as np
from src.embeddings import create_embedding, create_embeddings_batch


class TestEmbeddings:
    """Test embedding generation."""

    def test_create_single_embedding(self):
        """Test creating a single embedding."""
        text = "This is a test document about machine learning."
        embedding = create_embedding(text)

        # Check type and shape
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_create_embedding_empty_string(self):
        """Test embedding generation with empty string."""
        embedding = create_embedding("")
        assert isinstance(embedding, list)
        assert len(embedding) == 384

    def test_create_embeddings_batch(self):
        """Test batch embedding generation."""
        texts = [
            "First document about AI",
            "Second document about machine learning",
            "Third document about neural networks"
        ]
        embeddings = create_embeddings_batch(texts, batch_size=2)

        # Check output
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)

    def test_embedding_similarity(self):
        """Test that similar texts have similar embeddings."""
        text1 = "Machine learning is a subset of AI"
        text2 = "AI includes machine learning"
        text3 = "The weather is sunny today"

        emb1 = np.array(create_embedding(text1))
        emb2 = np.array(create_embedding(text2))
        emb3 = np.array(create_embedding(text3))

        # Cosine similarity
        def cosine_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_12 = cosine_sim(emb1, emb2)
        sim_13 = cosine_sim(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_12 > sim_13

    def test_batch_size_parameter(self):
        """Test different batch sizes."""
        texts = ["Text " + str(i) for i in range(10)]

        embeddings1 = create_embeddings_batch(texts, batch_size=2)
        embeddings2 = create_embeddings_batch(texts, batch_size=5)

        # Results should be same regardless of batch size
        assert len(embeddings1) == len(embeddings2) == 10

        # First embedding should be identical
        assert np.allclose(embeddings1[0], embeddings2[0], atol=1e-6)
