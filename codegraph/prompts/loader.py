"""
-------------------------------
Prompt Loader
-------------------------------

This module provides utilities for loading prompt templates from files
and formatting them with variables.
"""
import os
import string
from pathlib import Path
from typing import Dict, Any, Optional


class PromptTemplate:
    """
    Template for an LLM prompt that can be formatted with variables.

    Attributes:
        template: The prompt template string
    """

    def __init__(self, template: str):
        """
        Initialize a new prompt template.

        Args:
            template: The prompt template string
        """
        self.template = template

    def format(self, **kwargs: Any) -> str:
        """
        Format the prompt template with the provided variables.

        Args:
            **kwargs: Variables to insert into the template

        Returns:
            The formatted prompt string
        """
        return string.Template(self.template).safe_substitute(**kwargs)


class PromptManager:
    """
    Manager for loading and caching prompt templates.

    Attributes:
        prompt_dir: Directory containing prompt template files
        templates: Dictionary of loaded templates
    """

    def __init__(self, prompt_dir: Optional[str] = None):
        """
        Initialize a new prompt manager.

        Args:
            prompt_dir: Directory containing prompt template files
        """
        if prompt_dir is None:
            # Default to the prompts directory relative to this file
            self.prompt_dir = Path(__file__).parent
        else:
            self.prompt_dir = Path(prompt_dir)

        self.templates: Dict[str, PromptTemplate] = {}

    def load_template(self, name: str) -> PromptTemplate:
        """
        Load a prompt template by name.

        Args:
            name: The name of the template to load

        Returns:
            The loaded prompt template

        Raises:
            FileNotFoundError: If the template file doesn't exist
        """
        # Check if we've already loaded this template
        if name in self.templates:
            return self.templates[name]

        # Look for the template file
        file_path = self.prompt_dir / f"{name}.txt"
        if not file_path.exists():
            raise FileNotFoundError(
                f"Prompt template '{name}' not found at {file_path}"
            )

        # Load and cache the template
        with open(file_path, "r", encoding="utf-8") as f:
            template = PromptTemplate(f.read())

        self.templates[name] = template
        return template

    def format_prompt(self, name: str, **kwargs: Any) -> str:
        """
        Load and format a prompt template.

        Args:
            name: The name of the template to load
            **kwargs: Variables to insert into the template

        Returns:
            The formatted prompt string
        """
        template = self.load_template(name)
        return template.format(**kwargs)
