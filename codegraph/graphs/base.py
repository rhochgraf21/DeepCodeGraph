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
import logging # Added
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
    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
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
        # Initialize logger if not already done at module level for base classes
        # For this specific change, ensuring logger is available for PlantUMLBase
        self.logger = logging.getLogger(__name__)


    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        """
        Save the generated PlantUML graph as an image using a public PlantUML web service.

        This method sends the PlantUML graph string to a web server (defaulting to
        http://www.plantuml.com/plantuml) which renders the diagram and returns an image.

        Args:
            graph: The generated PlantUML code (diagram syntax).
            output_path: Path to save the image to. Can be a directory or a specific file path.
            image_format: Optional image format (e.g., "png", "svg").
                          Currently, this implementation primarily focuses on PNG generation
                          as it's universally supported by the default public server.
                          Requesting other formats might result in a warning if not "png",
                          as the server URL is hardcoded for PNG for simplicity.
        """
        # --- Image Format Handling for Web Service ---
        # The public PlantUML server can generate various formats (PNG, SVG, TXT, etc.).
        # This implementation defaults to PNG because it's widely supported and previewable.
        # If a different image_format is requested, a warning is logged because the URL
        # construction below is specific to PNG (`/png/`).
        # A more advanced implementation might change the URL path based on `image_format`.
        if image_format and image_format.lower() != 'png':
            self.logger.warning(
                f"PlantUMLBase.save currently uses the public server's PNG endpoint. "
                f"Requested format was '{image_format}', but will attempt to fetch PNG. "
                "The output filename will reflect the requested format if different, but content will be PNG."
            )

        # Use 'png' for the server URL as it's the most reliably supported format for images.
        server_request_format = "png" 
        # However, use the user's requested image_format for the file extension,
        # or default to '.png' if none was specified or if it was something else.
        output_file_extension = f".{(image_format or 'png').lower()}"


        encoded = self._encode_plantuml(graph)
        # Construct the URL to fetch the PNG image from the PlantUML server.
        url = f"{self.plantuml_server}/{server_request_format}/{encoded}"

        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}{output_file_extension}" # Use determined extension
            )
            output_file = output_dir / output_filename
        else:
            output_file = Path(output_path)
            # Ensure the output file has the correct extension if a full path is given.
            # If the user specified 'diagram.svg', it should save as 'diagram.svg'.
            # If they specified 'diagram' and image_format is 'svg', it should be 'diagram.svg'.
            if output_file.suffix.lower() != output_file_extension:
                self.logger.info(f"Output path '{output_path}' suffix does not match requested/default format '{output_file_extension}'. Adjusting to '{output_file.stem}{output_file_extension}'.")
                output_file = output_file.with_suffix(output_file_extension)
            create_directory_if_not_exists(str(output_file.parent))


        response = requests.get(url)
        if response.status_code == 200:
            with open(output_file, "wb+") as f:
                f.write(response.content)
            self.logger.info(f"Graph saved to {output_file}")
        else:
            self.logger.error(f"Failed to download graph image: Error {response.status_code} from {url}")
            raise Exception(
                f"Failed to download graph image: Error {response.status_code} from {url}"
            )

    # Add module-level logger (if not already present, though it makes more sense here or at the top)
    # This was added to ensure logger is defined. If it's already at module top, this line is redundant.
    # logger = logging.getLogger(__name__) # This should ideally be at the top of the file.

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
