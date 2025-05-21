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
            # --- mmdc CLI Check ---
            # shutil.which("mmdc") checks if the 'mmdc' (Mermaid CLI tool) executable is
            # available in the system's PATH. This is crucial for local image rendering.
            # If mmdc is not found, a warning is logged, and image generation is skipped.
            if not shutil.which("mmdc"):
                self.logger.warning(
                    "Mermaid CLI (mmdc) not found in PATH. Skipping image generation. "
                    "Please install it to generate Mermaid images locally (e.g., npm install -g @mermaid-js/mermaid-cli)."
                )
                return # Exit if mmdc is not found, after saving the .mmd

            # Determine image output file path.
            # If output_path was a directory, image_output_file will be like '.../timestamp.svg'.
            # If output_path was a specific file, image_output_file will be that path with the correct image extension.
            if Path(output_path).is_dir():
                image_output_file = output_file.with_suffix(f".{image_format.lower()}")
            else:
                original_output_path = Path(output_path)
                if original_output_path.suffix[1:].lower() == image_format.lower():
                    image_output_file = original_output_path
                else:
                    image_output_file = original_output_path.with_suffix(f".{image_format.lower()}")

            # --- mmdc Command Construction ---
            # The command for mmdc is constructed as follows:
            #   `mmdc -i <input_mmd_file> -o <output_image_file>`
            # - `-i`: Specifies the input Mermaid definition file (.mmd).
            # - `-o`: Specifies the output file for the rendered image. The format (e.g., PNG, SVG)
            #         is typically inferred by mmdc from the output file's extension.
            cli_command = [
                "mmdc",
                "-i", str(output_file),         # Input .mmd file path
                "-o", str(image_output_file),   # Output image file path
            ]
            
            self.logger.info(f"Attempting to render Mermaid diagram to {image_output_file} using mmdc...")
            try:
                # --- mmdc Execution ---
                # subprocess.run executes the constructed mmdc command.
                # - `capture_output=True`: Captures stdout and stderr.
                # - `text=True`: Decodes stdout and stderr as text.
                # - `check=False`: Does not raise an exception for non-zero exit codes,
                #                  allowing for manual error handling based on `process.returncode`.
                process = subprocess.run(cli_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    self.logger.info(f"Mermaid image successfully saved to {image_output_file}")
                else:
                    # Log detailed error information if mmdc fails.
                    self.logger.error(
                        f"Failed to generate Mermaid image with mmdc. Return code: {process.returncode}\n"
                        f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                    )
            except FileNotFoundError: # This case should ideally be caught by shutil.which.
                self.logger.error("mmdc command not found, though shutil.which might have indicated otherwise. Ensure mmdc is correctly installed and in PATH.")
            except Exception as e:
                self.logger.error(f"An error occurred while running mmdc: {e}")
