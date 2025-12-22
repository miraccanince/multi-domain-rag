"""
Tests for authentication module.

Tests JWT-based authentication, user management, password hashing,
and token generation/verification.
"""

import pytest
import tempfile
import os
import time
from datetime import timedelta

from src.auth import (
    UserManager,
    create_access_token,
    verify_token,
    get_user_manager,
    pwd_context
)


class TestUserManager:
    """Test suite for UserManager class."""

    @pytest.fixture
    def temp_users_file(self):
        """Create a temporary users file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

    @pytest.fixture
    def user_manager(self, temp_users_file):
        """Create a UserManager instance for testing."""
        return UserManager(users_file=temp_users_file)

    def test_create_user(self, user_manager):
        """Test creating a new user."""
        user = user_manager.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            full_name="Test User"
        )

        assert user['username'] == "testuser"
        assert user['email'] == "test@example.com"
        assert user['full_name'] == "Test User"
        assert user['is_active'] is True
        assert user['is_admin'] is False
        assert 'hashed_password' not in user  # Should not return password
        assert 'created_at' in user

    def test_create_duplicate_user(self, user_manager):
        """Test that creating duplicate username raises error."""
        user_manager.create_user("testuser", "password123")

        with pytest.raises(ValueError, match="already exists"):
            user_manager.create_user("testuser", "password456")

    def test_password_hashing(self, user_manager):
        """Test that passwords are hashed correctly."""
        user_manager.create_user("testuser", "mypassword")

        # Password should be hashed in storage
        stored_user = user_manager.users['testuser']
        assert stored_user['hashed_password'] != "mypassword"
        assert stored_user['hashed_password'].startswith('$2b$')  # bcrypt prefix

        # Verify password works
        assert pwd_context.verify("mypassword", stored_user['hashed_password'])

    def test_authenticate_user_success(self, user_manager):
        """Test successful user authentication."""
        user_manager.create_user("testuser", "correctpassword")

        authenticated = user_manager.authenticate_user("testuser", "correctpassword")

        assert authenticated is not None
        assert authenticated['username'] == "testuser"
        assert 'hashed_password' not in authenticated

    def test_authenticate_user_wrong_password(self, user_manager):
        """Test authentication fails with wrong password."""
        user_manager.create_user("testuser", "correctpassword")

        authenticated = user_manager.authenticate_user("testuser", "wrongpassword")

        assert authenticated is None

    def test_authenticate_nonexistent_user(self, user_manager):
        """Test authentication fails for non-existent user."""
        authenticated = user_manager.authenticate_user("nonexistent", "password")

        assert authenticated is None

    def test_authenticate_inactive_user(self, user_manager):
        """Test authentication fails for inactive user."""
        user_manager.create_user("testuser", "password")
        user_manager.users['testuser']['is_active'] = False

        authenticated = user_manager.authenticate_user("testuser", "password")

        assert authenticated is None

    def test_get_user(self, user_manager):
        """Test retrieving user by username."""
        user_manager.create_user(
            username="testuser",
            password="password",
            email="test@example.com"
        )

        user = user_manager.get_user("testuser")

        assert user is not None
        assert user['username'] == "testuser"
        assert user['email'] == "test@example.com"
        assert 'hashed_password' not in user

    def test_get_nonexistent_user(self, user_manager):
        """Test getting non-existent user returns None."""
        user = user_manager.get_user("nonexistent")

        assert user is None

    def test_get_all_users(self, user_manager):
        """Test retrieving all users."""
        user_manager.create_user("user1", "pass1", email="user1@test.com")
        user_manager.create_user("user2", "pass2", email="user2@test.com")
        user_manager.create_user("user3", "pass3", email="user3@test.com")

        all_users = user_manager.get_all_users()

        assert len(all_users) == 3
        usernames = [u['username'] for u in all_users]
        assert 'user1' in usernames
        assert 'user2' in usernames
        assert 'user3' in usernames

        # Verify no passwords in results
        for user in all_users:
            assert 'hashed_password' not in user

    def test_user_persistence(self, temp_users_file):
        """Test that users persist to disk and load correctly."""
        # Create user manager and add user
        manager1 = UserManager(users_file=temp_users_file)
        manager1.create_user(
            username="testuser",
            password="password123",
            email="test@example.com"
        )

        # Create new manager instance (should load from disk)
        manager2 = UserManager(users_file=temp_users_file)

        user = manager2.get_user("testuser")
        assert user is not None
        assert user['username'] == "testuser"
        assert user['email'] == "test@example.com"

    def test_thread_safety(self, user_manager):
        """Test that user creation is thread-safe."""
        import threading

        def create_user(index):
            try:
                user_manager.create_user(f"user_{index}", f"password_{index}")
            except ValueError:
                pass  # Duplicate user is ok in concurrent scenario

        # Create users concurrently
        threads = [threading.Thread(target=create_user, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All users should be created
        assert len(user_manager.users) == 10


class TestJWTTokens:
    """Test suite for JWT token operations."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        token = create_access_token(data={"sub": "testuser"})

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_with_custom_expiration(self):
        """Test token creation with custom expiration."""
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(hours=1)
        )

        assert token is not None

    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        token = create_access_token(data={"sub": "testuser"})

        username = verify_token(token)

        assert username == "testuser"

    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        invalid_token = "invalid.token.string"

        username = verify_token(invalid_token)

        assert username is None

    def test_verify_expired_token(self):
        """Test that expired tokens are rejected."""
        # Create token with very short expiration
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )

        username = verify_token(token)

        assert username is None

    def test_token_without_subject(self):
        """Test that token without 'sub' claim returns None."""
        token = create_access_token(data={"other_field": "value"})

        username = verify_token(token)

        assert username is None

    def test_token_contains_expiration(self):
        """Test that token contains expiration claim."""
        from jose import jwt
        from src.auth import SECRET_KEY, ALGORITHM

        token = create_access_token(data={"sub": "testuser"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert 'exp' in payload
        assert payload['sub'] == "testuser"

    def test_multiple_tokens_for_different_users(self):
        """Test creating tokens for multiple users."""
        token1 = create_access_token(data={"sub": "user1"})
        token2 = create_access_token(data={"sub": "user2"})
        token3 = create_access_token(data={"sub": "user3"})

        assert verify_token(token1) == "user1"
        assert verify_token(token2) == "user2"
        assert verify_token(token3) == "user3"


class TestUserManagerSingleton:
    """Test suite for get_user_manager singleton."""

    def test_get_user_manager_singleton(self):
        """Test that get_user_manager returns singleton instance."""
        manager1 = get_user_manager()
        manager2 = get_user_manager()

        # Should be the same instance
        assert manager1 is manager2

    def test_singleton_preserves_users(self):
        """Test that singleton preserves users across calls."""
        manager1 = get_user_manager()

        # Create user (if not exists)
        try:
            manager1.create_user("singleton_test", "password123")
        except ValueError:
            pass  # User might already exist

        # Get manager again
        manager2 = get_user_manager()

        # Should have the user
        user = manager2.get_user("singleton_test")
        assert user is not None


class TestPasswordSecurity:
    """Test suite for password security features."""

    @pytest.fixture
    def temp_users_file(self):
        """Create a temporary users file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

    def test_password_not_stored_plaintext(self, temp_users_file):
        """Test that passwords are never stored in plaintext."""
        manager = UserManager(users_file=temp_users_file)
        manager.create_user("testuser", "mypassword123")

        # Check in-memory storage
        assert manager.users['testuser']['hashed_password'] != "mypassword123"

        # Check file storage
        import json
        with open(temp_users_file, 'r') as f:
            data = json.load(f)
            assert data['testuser']['hashed_password'] != "mypassword123"

    def test_different_passwords_different_hashes(self, temp_users_file):
        """Test that different passwords produce different hashes."""
        manager = UserManager(users_file=temp_users_file)
        manager.create_user("user1", "password1")
        manager.create_user("user2", "password2")

        hash1 = manager.users['user1']['hashed_password']
        hash2 = manager.users['user2']['hashed_password']

        assert hash1 != hash2

    def test_same_password_different_hashes(self, temp_users_file):
        """Test that same password produces different hashes (salt)."""
        manager = UserManager(users_file=temp_users_file)
        manager.create_user("user1", "samepassword")
        manager.create_user("user2", "samepassword")

        hash1 = manager.users['user1']['hashed_password']
        hash2 = manager.users['user2']['hashed_password']

        # Bcrypt adds random salt, so hashes should differ
        assert hash1 != hash2

        # But both should verify correctly
        assert pwd_context.verify("samepassword", hash1)
        assert pwd_context.verify("samepassword", hash2)
