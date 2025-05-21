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

# logger = logging.getLogger(__name__) # Module-level logger, can be used if self.logger isn't preferred


class GraphvizDiagram(GraphGenerator):
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
        self.format_name = "graphviz"    # Store format name
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
        
        # Extract Graphviz code (assuming it's wrapped in ```graphviz|dot ... ```)
        # Use re.IGNORECASE
        match = re.search(r"```(?:graphviz|dot)\n(.*?)\n```", llm_response, re.DOTALL | re.IGNORECASE)
        graphviz_code = match.group(1) if match else llm_response.strip()

        return graphviz_code

    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            # Incorporate diagram_type into the filename if it's not the default "class"
            type_suffix = f"_{self.diagram_type}" if self.diagram_type != "class" else ""
            base_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}{type_suffix}-{timestamp}"
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
                # --- graphviz Library Usage ---
                # Attempt to import the 'graphviz' Python library. This library provides an interface
                # to the Graphviz layout engines (like dot, neato, etc.).
                import graphviz 
                
                # Determine the final desired image file path.
                # e.g., if output_file is 'diagram.dot' and image_format is 'png', this will be 'diagram.png'.
                image_output_file = output_file.with_suffix(f".{image_format.lower()}")

                self.logger.info(f"Attempting to render Graphviz diagram to {image_output_file} using 'graphviz' library...")
                
                # `graphviz.Source(graph, format=...)`:
                #   - Creates a Source object from the DOT language string (`graph`).
                #   - `format`: Specifies the desired output format for the image (e.g., "png", "svg").
                #     The library will use this to call the appropriate Graphviz engine.
                s = graphviz.Source(graph, format=image_format.lower())
                
                # `s.render(filename=..., view=False, cleanup=True)`:
                #   - `filename`: The base name for the output file(s). The `graphviz` library
                #                 will append the format suffix (e.g., '.png') to this name.
                #                 We provide the path without the suffix.
                #   - `view=False`: Prevents the rendered graph from being automatically opened in a viewer.
                #   - `cleanup=True`: Removes the intermediate DOT file that the library creates
                #                   during rendering, keeping only the final image.
                s.render(filename=str(image_output_file.with_suffix('')), view=False, cleanup=True)

                # Check if the rendering was successful and the file was created.
                if image_output_file.exists():
                    self.logger.info(f"Graphviz image successfully saved to {image_output_file}")
                else:
                    # This case might occur if render() doesn't throw an error but still fails to create the file.
                    self.logger.error(f"Graphviz image file not found at expected path: {image_output_file} after rendering. Check Graphviz library behavior.")

            except ImportError:
                # --- ImportError Handling ---
                # This block is executed if the 'graphviz' Python library is not installed.
                # It logs a warning and skips image generation, as the necessary library is missing.
                self.logger.warning(
                    "The 'graphviz' Python library is not installed. Skipping image generation. "
                    "Please install it (e.g., 'pip install graphviz') and ensure Graphviz tools are in PATH."
                )
            except graphviz.ExecutableNotFound:
                # --- graphviz.ExecutableNotFound Handling ---
                # This specific exception from the 'graphviz' library is raised if the underlying
                # Graphviz executables (e.g., 'dot', 'neato') are not found in the system's PATH.
                # Even if the Python library is installed, the core Graphviz tools must also be installed.
                self.logger.error(
                    "Graphviz executables (e.g., 'dot') not found in PATH. Skipping image generation. "
                    "Please ensure Graphviz is installed and configured correctly."
                )
            except Exception as e:
                # Catch any other unexpected errors during the rendering process.
                self.logger.error(f"An error occurred while rendering Graphviz image: {e}")
