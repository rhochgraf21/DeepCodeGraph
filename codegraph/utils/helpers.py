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
