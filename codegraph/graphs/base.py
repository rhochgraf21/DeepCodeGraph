"""
-------------------------------
Graph Generators
-------------------------------

This module provides the abstract base class for all graph generators.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests
import zlib
from pathlib import Path
from datetime import datetime
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename


class GraphGenerator(ABC):
    """
    Abstract base class for all graph generators.

    This class defines the interface that all graph generators must implement.
    """

    @abstractmethod
    def generate(self, repository_data: Dict[str, Any]) -> str:
        """
        Generate a graph representation of the repository.

        Args:
            repository_data: Dictionary containing repository structure data

        Returns:
            The generated graph as a string in the appropriate format
        """
        pass

    @abstractmethod
    def save(self, graph: str, output_path: str) -> None:
        """
        Save the generated graph to a file.

        Args:
            graph: The generated graph
            output_path: Path to save the graph to
        """
        pass


class PlantUMLBase(GraphGenerator):
    """
    Base class for PlantUML-based graph generators.

    This class provides common functionality for PlantUML-based graph generators.
    """

    def __init__(self, plantuml_server: str = "http://www.plantuml.com/plantuml"):
        """
        Initialize a new PlantUML-based graph generator.

        Args:
            plantuml_server: URL of the PlantUML server to use
        """
        self.plantuml_server = plantuml_server

    def save(self, graph: str, output_path: str) -> None:
        """
        Save the generated PlantUML graph as an image.

        Args:
            graph: The generated PlantUML code
            output_path: Path to save the image to
        """

        # Use the PlantUML compression algorithm
        encoded = self._encode_plantuml(graph)
        url = f"{self.plantuml_server}/png/{encoded}"

        # Ensure output directory exists
        output_dir = create_directory_if_not_exists(output_path)

        # Generate a filename if the output_path is a directory
        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}.png"
            )
            output_file = output_dir / output_filename
        else:
            output_file = Path(output_path)

        # Download the image
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_file, "wb+") as f:
                f.write(response.content)
            print(f"Graph saved to {output_path}")
        else:
            raise Exception(
                f"Failed to download graph image: Error {response.status_code}"
            )

    @staticmethod
    def _encode6bit(b: int) -> str:
        """Encode a 6-bit value as a character."""
        if b < 10:
            return chr(48 + b)
        b -= 10
        if b < 26:
            return chr(65 + b)
        b -= 26
        if b < 26:
            return chr(97 + b)
        b -= 26
        if b == 0:
            return "-"
        if b == 1:
            return "_"
        return "?"

    def _encode_plantuml(self, plantuml_text: str) -> str:
        """
        Compress and encode PlantUML text using the PlantUML algorithm.

        Args:
            plantuml_text: The PlantUML code to encode

        Returns:
            The encoded PlantUML code
        """
        import zlib

        compressed = zlib.compress(plantuml_text.encode("utf-8"))
        compressed = compressed[2:-4]  # Remove header and checksum

        encoded = ""
        i = 0
        while i < len(compressed):
            b1 = compressed[i]
            b2 = compressed[i + 1] if i + 1 < len(compressed) else 0
            b3 = compressed[i + 2] if i + 2 < len(compressed) else 0
            i += 3

            c1 = b1 >> 2
            c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
            c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
            c4 = b3 & 0x3F

            encoded += (
                self._encode6bit(c1)
                + self._encode6bit(c2)
                + self._encode6bit(c3)
                + self._encode6bit(c4)
            )

        return encoded
