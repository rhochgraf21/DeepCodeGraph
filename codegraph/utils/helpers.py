# utils/helpers.py - Add utility functions
"""
-------------------------------
Utility Functions
-------------------------------

This module provides helper functions used across the codebase.
"""
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import hashlib # Added

logger = logging.getLogger(__name__)

def create_directory_if_not_exists(path: str) -> Path:
    """
    Create a directory if it doesn't exist.

    Args:
        path: Path to the directory

    Returns:
        Path object for the directory

    Raises:
        IOError: If the directory cannot be created
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def is_valid_file_extension(filename: str, extensions: Set[str]) -> bool:
    """
    Check if a filename has one of the given extensions.

    Args:
        filename: Name of the file to check
        extensions: Set of valid extensions (including the dot)

    Returns:
        True if the file has a valid extension, False otherwise
    """
    return any(filename.endswith(ext) for ext in extensions)

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to ensure it's valid across platforms.

    Args:
        filename: Name to sanitize

    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    return re.sub(r'[\\/*?:"<>|]', "_", filename)


def calculate_file_hash(filepath: Path, hash_algo: str = "sha256") -> str:
    """
    Calculate the hash of a file's content.

    Args:
        filepath: Path to the file.
        hash_algo: The hashing algorithm to use (default: "sha256").
                   Can be any algorithm supported by hashlib.

    Returns:
        Hexadecimal string representation of the hash.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
    h = hashlib.new(hash_algo)
    try:
        with open(filepath, "rb") as f:
            while True:
                # Read file in chunks to handle large files efficiently
                chunk = f.read(8192) # 8KB chunks
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found when calculating hash: {filepath}")
        raise
    except IOError as e:
        logger.error(f"IOError when calculating hash for {filepath}: {e}")
        raise
