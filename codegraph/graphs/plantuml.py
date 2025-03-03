"""
-------------------------------
PlantUML Diagram Generator
-------------------------------

This module provides a generator for creating PlantUML diagrams
from repository structure data.
"""
import json
import re
from typing import Dict, Any, List, Optional
import logging

from codegraph.graphs.base import PlantUMLBase
from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager

logger = logging.getLogger(__name__)


class PlantUMLActivityDiagram(PlantUMLBase):
    """
    Generator for PlantUML activity diagrams.

    This class provides functionality for generating PlantUML activity diagrams
    from repository structure data.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        token_limit: int = 128000,
        fallback_threshold: float = 0.9,
        **kwargs,
    ):
        """
        Initialize a new PlantUML activity diagram generator.

        Args:
            token_limit: Maximum token limit for the LLM provider
            fallback_threshold: Threshold for falling back to file-by-file diagrams
            **kwargs: Additional arguments to pass to the base class
        """
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold

    def _count_tokens(self, text: str) -> int:
        """
        Rough estimation of token count.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Simple word-based estimation
        return len(text.split())

    def generate(self, repository_data: Dict[str, Any]) -> str:
        """
        Generate a PlantUML activity diagram from repository data.

        Args:
            repository_data: Dictionary containing repository structure data

        Returns:
            The generated PlantUML code
        """

        prompt_manager = PromptManager()

        # Check if we need to generate per-file diagrams
        serialized = json.dumps(repository_data, indent=2)
        tokens = self._count_tokens(serialized)
        logger.info(f"Token count: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            logger.info(
                "Token count exceeds threshold. Generating diagrams per file..."
            )
            # Future enhancement: return multiple diagrams for large repositories
            # For now, just take the first file
            file_data = next(iter(repository_data["files"].values()))
            prompt = prompt_manager.format_prompt(
                "plantuml_diagram", repository=json.dumps(file_data, indent=2)
            )
        else:
            prompt = prompt_manager.format_prompt(
                "plantuml_diagram", repository=serialized
            )

        # Generate the diagram
        plantuml_response = self.llm_provider.query(prompt)

        # Extract the PlantUML code
        match = re.search(r"```plantuml\n(.*?)\n```", plantuml_response, re.DOTALL)
        plantuml_code = match.group(1) if match else plantuml_response.strip()

        return plantuml_code


class PlantUMLClassDiagram(PlantUMLBase):
    """
    Generator for PlantUML class diagrams.

    This class provides functionality for generating PlantUML class diagrams
    from repository structure data.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        token_limit: int = 128000,
        fallback_threshold: float = 0.9,
        **kwargs,
    ):
        """
        Initialize a new PlantUML activity diagram generator.

        Args:
            token_limit: Maximum token limit for the LLM provider
            fallback_threshold: Threshold for falling back to file-by-file diagrams
            **kwargs: Additional arguments to pass to the base class
        """
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold

    def generate(self, repository_data: Dict[str, Any]) -> str:
        """
        Generate a PlantUML class diagram from repository data.

        Args:
            repository_data: Dictionary containing repository structure data

        Returns:
            The generated PlantUML code
        """
        classes = {}

        # Collect classes from each file
        for file_name, file_data in repository_data["files"].items():
            for cls in file_data.get("classes", []):
                classes[cls["name"]] = cls

        uml_lines = [
            "@startuml",
            "hide empty members",
            "skinparam classAttributeIconSize 0",
        ]

        # Define each class with its methods and type hints
        for class_name, cls in classes.items():
            uml_lines.append(f"class {class_name} {{")
            for method in cls.get("methods", []):
                # Show parameter types and return type if available
                params = ", ".join(
                    [
                        f"{p.get('name', '')}: {p.get('type', 'Any')}"
                        for p in method.get("parameters", [])
                    ]
                )
                ret = method.get("return_type") or "None"
                uml_lines.append(f"  + {method.get('name')}({params}) : {ret}")
            uml_lines.append("}")

        # Add relationships based on inheritance and composition patterns
        uml_lines = self._add_relationships(uml_lines, classes, repository_data)

        uml_lines.append("@enduml")
        return "\n".join(uml_lines)

    def _add_relationships(
        self,
        uml_lines: List[str],
        classes: Dict[str, Any],
        repository_data: Dict[str, Any],
    ) -> List[str]:
        """
        Add relationships between classes based on inheritance and composition patterns.
        """
        prompt_manager = PromptManager()
        prompt = prompt_manager.format_prompt(
            "class_diagram", uml_lines=uml_lines, repository=repository_data
        )
        plantuml_response = self.llm_provider.query(prompt)

        match = re.search(r"```plantuml\n(.*?)\n```", plantuml_response, re.DOTALL)
        plantuml_code = match.group(1) if match else plantuml_response.strip()

        uml_lines += plantuml_code.splitlines()

        return uml_lines
