from codegraph.graphs.base import GraphGenerator
from typing import Dict, Any
import json
import re
import logging
from pathlib import Path # Import Path
from datetime import datetime # Import datetime

from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename # Import helpers

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

    def _count_tokens(self, text: str) -> int:
        return len(text.split())

    def generate(self, repository_data: Dict[str, Any]) -> str:
        prompt_manager = PromptManager()
        serialized_data = json.dumps(repository_data, indent=2)
        tokens = self._count_tokens(serialized_data)
        logger.info(f"Token count for MermaidDiagram: {tokens}")

        if tokens > self.token_limit * self.fallback_threshold:
            logger.info(
                "Token count exceeds threshold for MermaidDiagram. "
                "Generating diagram for the first file only (placeholder behavior)."
            )
            try:
                first_file_key = next(iter(repository_data.get("files", {})))
                file_data = repository_data["files"][first_file_key]
                prompt_input = json.dumps(file_data, indent=2)
            except StopIteration:
                logger.warning("No files found in repository_data for MermaidDiagram.")
                prompt_input = "{}"
        else:
            prompt_input = serialized_data

        prompt = prompt_manager.format_prompt(
            "mermaid_diagram", repository=prompt_input
        )

        llm_response = self.llm_provider.query(prompt)
        match = re.search(r"```mermaid\n(.*?)\n```", llm_response, re.DOTALL) # Corrected regex
        mermaid_code = match.group(1) if match else llm_response.strip()
        return mermaid_code

    def save(self, graph: str, output_path: str) -> None:
        output_dir = create_directory_if_not_exists(output_path)

        if Path(output_path).is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = sanitize_filename(
                f"dcg-{self.__class__.__name__}-{timestamp}.mmd" # Ensure .mmd extension
            )
            output_file = output_dir / output_filename
        else:
            output_file = Path(output_path)
            # Ensure the parent directory of the output file exists if a full path is given
            create_directory_if_not_exists(str(output_file.parent))


        try:
            with open(output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            print(f"Mermaid diagram saved to {output_file}")
        except IOError as e:
            logger.error(f"Failed to save Mermaid diagram to {output_file}: {e}")
            raise # Re-raise the exception to notify the caller
