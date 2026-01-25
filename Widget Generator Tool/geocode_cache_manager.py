"""Cache Manager for Geocode Results."""

import threading
import json
import os
from typing import Optional


class _GeocodeCacheManager:
    """Thread-safe geocode cache manager."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, _cache: Optional[dict] = None):
        self._cache = _cache or {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = {}
        return cls._instance

    def load(self) -> None:
        """Load cache from disk."""
        path = _geocode_cache_path()
        if not os.path.exists(path):
            self._cache = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self._cache = json.load(fh)
        except (
            FileNotFoundError,
            PermissionError,
            IOError,
            OSError,
            ValueError,
            TypeError,
        ):
            self._cache = {}

    def save(self) -> None:
        """Save cache to disk. Well duh"""
        path = _geocode_cache_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, ensure_ascii=False, indent=2)
        except (
            FileNotFoundError,
            PermissionError,
            IOError,
            OSError,
            ValueError,
            TypeError,
        ):
            print("⚠ Warning: Could not save geocode cache to disk.")
            return

    def get(self, key: str):
        """Retrieve value from cache by key."""
        return self._cache.get(key)

    def set(self, key: str, value) -> None:
        """Set value in cache by key."""
        self._cache[key] = value

    def get_all(self) -> dict:
        """Fetch all cache."""
        return self._cache


def _geocode_cache_path() -> str:
    public_dir = os.path.join(os.path.dirname(__file__), "public")
    if not os.path.exists(public_dir):
        try:
            os.makedirs(public_dir, exist_ok=True)
        except (OSError, PermissionError):
            print("Could not create public directory for geocode cache.")
    return os.path.join(public_dir, "geocode_cache.json")
