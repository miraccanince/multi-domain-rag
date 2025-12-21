"""
Authentication Module

JWT-based authentication system for user management and access control.
Includes user registration, login, token generation and validation.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from pathlib import Path
import threading

from passlib.context import CryptContext
from jose import JWTError, jwt

# Security configuration
SECRET_KEY = "your-secret-key-change-this-in-production"  # TODO: Move to environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserManager:
    """
    Manages user accounts with simple JSON file storage.

    In production, this should use a proper database.
    """

    def __init__(self, users_file: str = "users.json"):
        """
        Initialize user manager.

        Args:
            users_file: Path to users storage file
        """
        self.users_file = Path(__file__).parent.parent / users_file
        self.users: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        # Load existing users
        self._load_users()

    def _load_users(self):
        """Load users from disk."""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
                print(f"Loaded {len(self.users)} users")
            except Exception as e:
                print(f"Warning: Could not load users: {e}")
                self.users = {}
        else:
            self.users = {}

    def _save_users(self):
        """Save users to disk."""
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save users: {e}")

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user account.

        Args:
            username: Unique username
            password: Plain text password (will be hashed)
            email: Optional email address
            full_name: Optional full name

        Returns:
            User data (without password)

        Raises:
            ValueError: If username already exists
        """
        with self.lock:
            # Check if user exists
            if username in self.users:
                raise ValueError(f"Username '{username}' already exists")

            # Hash password
            hashed_password = pwd_context.hash(password)

            # Create user entry
            user_data = {
                'username': username,
                'hashed_password': hashed_password,
                'email': email,
                'full_name': full_name,
                'created_at': datetime.now().isoformat(),
                'is_active': True,
                'is_admin': False
            }

            # Store user
            self.users[username] = user_data
            self._save_users()

            # Return user without password
            return self._user_without_password(user_data)

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User data (without password) if authentication successful, None otherwise
        """
        user = self.users.get(username)
        if not user:
            return None

        if not pwd_context.verify(password, user['hashed_password']):
            return None

        if not user.get('is_active', True):
            return None

        return self._user_without_password(user)

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username.

        Args:
            username: Username to look up

        Returns:
            User data (without password) if found, None otherwise
        """
        user = self.users.get(username)
        if user:
            return self._user_without_password(user)
        return None

    def _user_without_password(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Return user data without password field."""
        return {k: v for k, v in user.items() if k != 'hashed_password'}

    def get_all_users(self) -> list[Dict[str, Any]]:
        """Get list of all users (without passwords)."""
        return [self._user_without_password(user) for user in self.users.values()]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Data to encode in token (typically {'sub': username})
        expires_delta: Token expiration time delta

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT token and extract username.

    Args:
        token: JWT token string

    Returns:
        Username if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError as e:
        print(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None


# Singleton user manager
_user_manager: Optional[UserManager] = None
_manager_lock = threading.Lock()


def get_user_manager() -> UserManager:
    """Get or create the global user manager instance."""
    global _user_manager

    if _user_manager is None:
        with _manager_lock:
            if _user_manager is None:
                _user_manager = UserManager()

    return _user_manager
