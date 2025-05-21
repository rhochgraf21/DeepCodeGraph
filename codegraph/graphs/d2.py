from codegraph.graphs.base import GraphGenerator
from typing import Dict, Any, Optional 
import json
import re
import logging
from pathlib import Path
from datetime import datetime
import subprocess 
import shutil 

from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename

# logger = logging.getLogger(__name__) # Module-level logger, can be used if self.logger isn't preferred


class D2Diagram(GraphGenerator):
    def __init__(
        self,
        llm_provider: LLMProvider,
        diagram_type: str = "class", # New parameter
        token_limit: int = 128000,
        fallback_threshold: float = 0.9,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.diagram_type = diagram_type # Store it
        self.format_name = "d2"          # Store format name
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold
        self.logger = logging.getLogger(__name__) # Ensure logger is initialized

    def _count_tokens(self, text: str) -> int:
        return len(text.split())

    def generate(self, repository_data: Dict[str, Any]) -> str:
        prompt_manager = PromptManager()
        serialized_data = json.dumps(repository_data, indent=2)
        tokens = self._count_tokens(serialized_data)
        self.logger.info(f"Token count for {self.format_name} {self.diagram_type}: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            self.logger.info(
                f"Token count exceeds threshold for {self.format_name} {self.diagram_type}. "
                "Generating diagram for the first file only (placeholder behavior)."
            )
            try:
                first_file_key = next(iter(repository_data.get("files", {})))
                file_data = repository_data["files"][first_file_key]
                prompt_input = json.dumps(file_data, indent=2)
            except StopIteration:
                self.logger.warning(f"No files found in repository_data for {self.format_name} {self.diagram_type}.")
                prompt_input = "{}"
        else:
            prompt_input = serialized_data
        
        prompt_name = f"{self.format_name}_{self.diagram_type}_diagram"
        self.logger.info(f"Using prompt: {prompt_name}")

        prompt = prompt_manager.format_prompt(
            prompt_name, repository=prompt_input
        )

        llm_response = self.llm_provider.query(prompt)
        
        # Extract D2 code (assuming it's wrapped in ```d2 ... ```)
        # Use re.IGNORECASE
        match = re.search(r"```d2\n(.*?)\n```", llm_response, re.DOTALL | re.IGNORECASE)
        d2_code = match.group(1) if match else llm_response.strip()

        return d2_code
        
    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            # Incorporate diagram_type into the filename if it's not the default "class"
            type_suffix = f"_{self.diagram_type}" if self.diagram_type != "class" else ""
            base_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}{type_suffix}-{timestamp}"
            )
            d2_output_filename = f"{base_filename}.d2"
            output_file = output_dir / d2_output_filename 
        else:
            output_file_path = Path(output_path)
            create_directory_if_not_exists(str(output_file_path.parent))
            output_file = output_file_path.with_suffix(".d2")

        try:
            with open(output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            self.logger.info(f"D2 diagram text saved to {output_file}")
        except IOError as e:
            self.logger.error(f"Failed to save D2 diagram text to {output_file}: {e}")
            raise
            
        if image_format:
            # --- d2 CLI Check ---
            # shutil.which("d2") checks if the 'd2' command-line tool executable is
            # available in the system's PATH. This is essential for local D2 diagram rendering.
            # If 'd2' is not found, a warning is logged, and image generation is skipped.
            if not shutil.which("d2"):
                self.logger.warning(
                    "D2 CLI (d2) not found in PATH. Skipping image generation. "
                    "Please install D2 to generate D2 images locally (https://d2lang.com/tour/install)."
                )
                return # Exit if d2 is not found, after saving the .d2 file

            # D2 infers the output image format from the extension of the output file.
            # Thus, image_output_file is set to have the extension specified by image_format (e.g., ".svg", ".png").
            image_output_file = output_file.with_suffix(f".{image_format.lower()}")
            
            # --- d2 Command Construction ---
            # The command for the D2 CLI is typically: `d2 <input_d2_file> <output_image_file>`
            #   - `<input_d2_file>`: Path to the D2 definition file (.d2).
            #   - `<output_image_file>`: Path where the rendered image should be saved. D2 uses this
            #                            file's extension to determine the output format.
            # An optional layout engine can be specified with `--layout <engine_name>` (e.g., "elk", "dagre").
            # Default is "dagre". We omit it here to use the default.
            cli_command = [
                "d2",
                # "--layout", "elk", # Example: uncomment to use ELK layout engine
                str(output_file),         # Input .d2 file path
                str(image_output_file),   # Output image file path (e.g., diagram.svg)
            ]

            self.logger.info(f"Attempting to render D2 diagram to {image_output_file} using d2 CLI...")
            try:
                # --- d2 CLI Execution ---
                # subprocess.run executes the D2 command.
                # - `capture_output=True`: Captures stdout and stderr.
                # - `text=True`: Decodes stdout and stderr as text.
                # - `check=False`: Prevents raising an exception for non-zero exit codes,
                #                  allowing for custom handling of errors based on `process.returncode`.
                process = subprocess.run(cli_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    # D2 CLI might produce output to stdout/stderr even on success (e.g., theme loading messages).
                    # The most reliable check for success is the exit code (0) and the existence of the output file.
                    if image_output_file.exists():
                         self.logger.info(f"D2 image successfully saved to {image_output_file}")
                    else:
                         # This case handles scenarios where d2 exits cleanly but the file isn't created.
                         self.logger.warning(f"D2 CLI reported success (code 0) but output file {image_output_file} not found. CLI output:\nStdout: {process.stdout}\nStderr: {process.stderr}")
                else:
                    # Log detailed error information if d2 CLI fails.
                    self.logger.error(
                        f"Failed to generate D2 image with d2 CLI. Return code: {process.returncode}\n"
                        f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                    )
            except FileNotFoundError: # This should ideally be caught by shutil.which.
                self.logger.error("D2 CLI (d2) command not found, though shutil.which might have indicated otherwise. Ensure d2 is correctly installed and in PATH.")
            except Exception as e:
                self.logger.error(f"An error occurred while running d2 CLI: {e}")
