from codegraph.graphs.base import GraphGenerator
from typing import Dict, Any, Optional
import json
import re
import logging
from pathlib import Path
from datetime import datetime
import subprocess # Added
import shutil # Added

from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename

logger = logging.getLogger(__name__)


class MermaidDiagram(GraphGenerator):
    def __init__(
        self,
        llm_provider: LLMProvider,
        token_limit: int = 128000,
        fallback_threshold: float = 0.9,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold
        self.logger = logger

    def _count_tokens(self, text: str) -> int:
        return len(text.split())

    def generate(self, repository_data: Dict[str, Any]) -> str:
        prompt_manager = PromptManager()
        serialized_data = json.dumps(repository_data, indent=2)
        tokens = self._count_tokens(serialized_data)
        self.logger.info(f"Token count for MermaidDiagram: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            self.logger.info(
                "Token count exceeds threshold for MermaidDiagram. "
                "Generating diagram for the first file only (placeholder behavior)."
            )
            try:
                first_file_key = next(iter(repository_data.get("files", {})))
                file_data = repository_data["files"][first_file_key]
                prompt_input = json.dumps(file_data, indent=2)
            except StopIteration:
                self.logger.warning("No files found in repository_data for MermaidDiagram.")
                prompt_input = "{}"
        else:
            prompt_input = serialized_data

        prompt = prompt_manager.format_prompt(
            "mermaid_diagram", repository=prompt_input
        )

        llm_response = self.llm_provider.query(prompt)
        match = re.search(r"```mermaid\n(.*?)\n```", llm_response, re.DOTALL)
        mermaid_code = match.group(1) if match else llm_response.strip()
        return mermaid_code

    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        # Determine the path for the .mmd file
        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            # Base filename for both .mmd and potential image
            base_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}"
            )
            mmd_output_filename = f"{base_filename}.mmd"
            output_file = output_dir / mmd_output_filename # Path to .mmd file
        else:
            # output_path is a specific file path
            output_file_path = Path(output_path)
            create_directory_if_not_exists(str(output_file_path.parent))
            # Set output_file to be the .mmd version of the path
            output_file = output_file_path.with_suffix(".mmd")


        try:
            with open(output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            self.logger.info(f"Mermaid diagram text saved to {output_file}")
        except IOError as e:
            self.logger.error(f"Failed to save Mermaid diagram text to {output_file}: {e}")
            raise
        
        if image_format:
            if not shutil.which("mmdc"):
                self.logger.warning(
                    "Mermaid CLI (mmdc) not found in PATH. Skipping image generation. "
                    "Please install it to generate Mermaid images locally."
                )
                return # Exit if mmdc is not found, after saving the .mmd

            # Determine image output file path
            if Path(output_path).is_dir():
                # output_file is already .../timestamp.mmd
                # image_output_file should be .../timestamp.svg (or .png)
                image_output_file = output_file.with_suffix(f".{image_format.lower()}")
            else:
                # output_path was a specific file path e.g. /path/to/diagram.svg or /path/to/diagram
                # output_file is /path/to/diagram.mmd
                # image_output_file should be original output_path if suffix matches image_format,
                # or output_path with new suffix.
                original_output_path = Path(output_path)
                if original_output_path.suffix.lower() == f".{image_format.lower()}":
                    image_output_file = original_output_path
                else:
                    image_output_file = original_output_path.with_suffix(f".{image_format.lower()}")

            cli_command = [
                "mmdc",
                "-i",
                str(output_file),         # Input .mmd file
                "-o",
                str(image_output_file),   # Output image file
            ]
            # According to mmdc docs, -f is for puppeteerConfigFile, not format.
            # Format is typically inferred from output file extension.
            # If explicit format control is needed (e.g. for stdout), -e <format> is used.
            # For file output, -o with correct extension is usually sufficient.

            self.logger.info(f"Attempting to render Mermaid diagram to {image_output_file} using mmdc...")
            try:
                process = subprocess.run(cli_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    self.logger.info(f"Mermaid image successfully saved to {image_output_file}")
                else:
                    self.logger.error(
                        f"Failed to generate Mermaid image with mmdc. Return code: {process.returncode}\n"
                        f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                    )
            except FileNotFoundError: # Should be caught by shutil.which, but as a fallback
                self.logger.error("mmdc command not found. Please ensure it is installed and in your PATH.")
            except Exception as e:
                self.logger.error(f"An error occurred while running mmdc: {e}")
