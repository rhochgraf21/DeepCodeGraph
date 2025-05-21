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


class D2Diagram(GraphGenerator):
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
        self.logger.info(f"Token count for D2Diagram: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            self.logger.info(
                "Token count exceeds threshold for D2Diagram. "
                "Generating diagram for the first file only (placeholder behavior)."
            )
            try:
                first_file_key = next(iter(repository_data.get("files", {})))
                file_data = repository_data["files"][first_file_key]
                prompt_input = json.dumps(file_data, indent=2)
            except StopIteration:
                self.logger.warning("No files found in repository_data for D2Diagram.")
                prompt_input = "{}"
        else:
            prompt_input = serialized_data

        prompt = prompt_manager.format_prompt(
            "d2_diagram", repository=prompt_input
        )

        llm_response = self.llm_provider.query(prompt)
        match = re.search(r"```d2\n(.*?)\n```", llm_response, re.DOTALL)
        d2_code = match.group(1) if match else llm_response.strip()
        return d2_code
        
    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}"
            )
            d2_output_filename = f"{base_filename}.d2"
            output_file = output_dir / d2_output_filename # Path to .d2 file
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
            if not shutil.which("d2"):
                self.logger.warning(
                    "D2 CLI (d2) not found in PATH. Skipping image generation. "
                    "Please install D2 to generate D2 images locally (https://d2lang.com/tour/install)."
                )
                return # Exit if d2 is not found, after saving the .d2 file

            # D2 derives the output format from the output file's extension.
            # So, image_output_file needs to have the correct extension.
            image_output_file = output_file.with_suffix(f".{image_format.lower()}")
            
            cli_command = [
                "d2",
                # "--layout", "elk", # Optional: specify layout engine if needed, default is dagre
                str(output_file),         # Input .d2 file path
                str(image_output_file),   # Output image file path
            ]

            self.logger.info(f"Attempting to render D2 diagram to {image_output_file} using d2 CLI...")
            try:
                process = subprocess.run(cli_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    # D2 CLI might print "Generating [theme name] [output_path]..." to stdout on success
                    # and might not print anything for some formats if successful.
                    # Stderr might contain theme loading errors even on success for some OS/setups.
                    # So, primary check is returncode.
                    if image_output_file.exists():
                         self.logger.info(f"D2 image successfully saved to {image_output_file}")
                    else:
                         self.logger.warning(f"D2 CLI reported success (code 0) but output file {image_output_file} not found. CLI output:\nStdout: {process.stdout}\nStderr: {process.stderr}")

                else:
                    self.logger.error(
                        f"Failed to generate D2 image with d2 CLI. Return code: {process.returncode}\n"
                        f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                    )
            except FileNotFoundError: # Should be caught by shutil.which, but as a fallback
                self.logger.error("D2 CLI (d2) command not found. Please ensure it is installed and in your PATH.")
            except Exception as e:
                self.logger.error(f"An error occurred while running d2 CLI: {e}")
