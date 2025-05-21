from codegraph.graphs.base import GraphGenerator
from typing import Dict, Any, Optional
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename

logger = logging.getLogger(__name__)


class GraphvizDiagram(GraphGenerator):
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
        self.logger.info(f"Token count for GraphvizDiagram: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            self.logger.info(
                "Token count exceeds threshold for GraphvizDiagram. "
                "Generating diagram for the first file only (placeholder behavior)."
            )
            try:
                first_file_key = next(iter(repository_data.get("files", {})))
                file_data = repository_data["files"][first_file_key]
                prompt_input = json.dumps(file_data, indent=2)
            except StopIteration:
                self.logger.warning("No files found in repository_data for GraphvizDiagram.")
                prompt_input = "{}"
        else:
            prompt_input = serialized_data

        prompt = prompt_manager.format_prompt(
            "graphviz_diagram", repository=prompt_input
        )

        llm_response = self.llm_provider.query(prompt)
        match = re.search(r"```(?:graphviz|dot)\n(.*?)\n```", llm_response, re.DOTALL)
        graphviz_code = match.group(1) if match else llm_response.strip()
        return graphviz_code

    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}"
            )
            dot_output_filename = f"{base_filename}.dot"
            output_file = output_dir / dot_output_filename # Path to .dot file
        else:
            output_file_path = Path(output_path)
            create_directory_if_not_exists(str(output_file_path.parent))
            output_file = output_file_path.with_suffix(".dot")

        try:
            with open(output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            self.logger.info(f"Graphviz diagram text saved to {output_file}")
        except IOError as e:
            self.logger.error(f"Failed to save Graphviz diagram text to {output_file}: {e}")
            raise
        
        if image_format:
            try:
                import graphviz # Try to import the library
                
                # Determine the final desired image path
                image_output_file = output_file.with_suffix(f".{image_format.lower()}")

                self.logger.info(f"Attempting to render Graphviz diagram to {image_output_file} using 'graphviz' library...")
                
                # Create Source object from the DOT string content, pass format directly
                s = graphviz.Source(graph, format=image_format.lower())
                
                # The 'filename' parameter for render should be the desired output filename *without* the extension.
                # render will append the format as a suffix.
                s.render(filename=str(image_output_file.with_suffix('')), view=False, cleanup=True)

                if image_output_file.exists():
                    self.logger.info(f"Graphviz image successfully saved to {image_output_file}")
                else:
                    self.logger.error(f"Graphviz image file not found at expected path: {image_output_file} after rendering. Check Graphviz library behavior.")

            except ImportError:
                self.logger.warning(
                    "The 'graphviz' Python library is not installed. Skipping image generation. "
                    "Please install it (e.g., 'pip install graphviz') and ensure Graphviz tools are in PATH."
                )
            except graphviz.ExecutableNotFound: # Specific exception for missing executables
                self.logger.error(
                    "Graphviz executables (e.g., 'dot') not found in PATH. Skipping image generation. "
                    "Please ensure Graphviz is installed and configured correctly."
                )
            except Exception as e:
                self.logger.error(f"An error occurred while rendering Graphviz image: {e}")
