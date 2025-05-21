import logging
from pathlib import Path
from typing import Optional
import os       # For checking environment variable for JAR path
import shutil   # For shutil.which to check for java executable
import subprocess # For running plantuml.jar

from codegraph.graphs.plantuml import PlantUMLActivityDiagram, PlantUMLClassDiagram
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename
from datetime import datetime

logger = logging.getLogger(__name__)

# --- Module-Level Comments ---
# This module provides functionality for generating PlantUML diagrams locally
# by directly invoking a local PlantUML JAR file using subprocess.
# It offers an alternative to the web-based PlantUML generation,
# useful for environments without internet access or for privacy.

# --- PLANTUML_JAR_PATH Logic ---
# Defines the path to the PlantUML JAR file.
# Users can specify a custom path by setting the 'PLANTUML_JAR' environment variable.
# If the environment variable is not set, it defaults to '/usr/local/bin/plantuml.jar'.
# This default path is based on common installation locations for PlantUML.
DEFAULT_PLANTUML_JAR_PATH = "/usr/local/bin/plantuml.jar"
PLANTUML_JAR_PATH = os.environ.get("PLANTUML_JAR", DEFAULT_PLANTUML_JAR_PATH)

class PlantUMLLocalSaveMixin:
    """
    Mixin class to provide local PlantUML saving functionality using a local plantuml.jar.
    Assumes 'self.logger' is available from the class using this mixin.
    """
    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        image_format = (image_format or "png").lower()

        output_dir = create_directory_if_not_exists(output_path)
        base_filename_stem = ""
        specified_output_is_dir = Path(output_path).is_dir()

        if specified_output_is_dir:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base_filename_stem = sanitize_filename(f"dcg-{self.__class__.__name__}-{timestamp}")
            text_output_file = output_dir / f"{base_filename_stem}.puml"
            image_output_file = output_dir / f"{base_filename_stem}.{image_format}"
        else:
            p_output_path = Path(output_path)
            create_directory_if_not_exists(str(p_output_path.parent))
            if p_output_path.suffix[1:].lower() == image_format:
                base_filename_stem = p_output_path.stem
                image_output_file = p_output_path
                text_output_file = p_output_path.with_suffix(".puml")
            else:
                base_filename_stem = p_output_path.stem if p_output_path.suffix else p_output_path.name
                image_output_file = p_output_path.with_suffix(f".{image_format}")
                text_output_file = p_output_path.with_suffix(".puml")
                if image_output_file == text_output_file and image_format != "puml":
                     text_output_file = image_output_file.parent / (image_output_file.stem + "_text.puml")

        # First, always try to save the .puml text file.
        self._save_plantuml_text(graph, str(text_output_file), image_format, is_error_fallback=False)

        # --- Local Image Rendering using plantuml.jar ---

        # Check for Java executable
        if not shutil.which("java"):
            self.logger.error("Java executable not found in PATH. Cannot run PlantUML JAR. Skipping image generation.")
            # Text file is already saved. No need to call _save_plantuml_text again as a fallback.
            return

        # Check for PlantUML JAR existence.
        if not Path(PLANTUML_JAR_PATH).is_file():
            self.logger.error(
                f"PlantUML JAR not found at {PLANTUML_JAR_PATH}. Cannot generate PlantUML diagram locally. "
                f"Ensure plantuml.jar is at this location or set PLANTUML_JAR environment variable."
            )
            # Text file is already saved. No need to call _save_plantuml_text again as a fallback.
            return
        
        # Construct the command for subprocess.run()
        # Note: PlantUML JAR typically creates the output file in the directory specified by -output,
        # and the output filename is derived from the input filename (text_output_file.stem).
        # So, image_output_file determined earlier should match what PlantUML creates.
        cli_command = [
            "java",
            "-jar",
            PLANTUML_JAR_PATH,
            "-t" + image_format.lower(),    # e.g., -tpng, -tsvg
            "-output",
            str(image_output_file.parent),  # Output directory
            str(text_output_file)           # Input .puml file
        ]

        self.logger.info(f"Attempting to render PlantUML diagram to {image_output_file.parent} using plantuml.jar...")
        try:
            process = subprocess.run(cli_command, capture_output=True, text=True, check=False)
            if process.returncode == 0:
                # Check if the expected output file was created
                if image_output_file.exists():
                    self.logger.info(f"PlantUML image successfully saved locally to {image_output_file}")
                else:
                    self.logger.error(
                        f"PlantUML JAR execution seemed successful (return code 0) but expected output file {image_output_file} was not found. "
                        f"This might indicate an issue with PlantUML's output naming or path handling. "
                        f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                    )
            else:
                self.logger.error(
                    f"Failed to generate PlantUML image with plantuml.jar. Return code: {process.returncode}\n"
                    f"Stdout: {process.stdout}\nStderr: {process.stderr}"
                )
        except FileNotFoundError: # For "java" not found, though shutil.which should catch it.
            self.logger.error("Java command not found. Please ensure Java is installed and in your PATH.")
        except Exception as e:
            self.logger.error(f"An error occurred while running plantuml.jar: {e}")


    def _save_plantuml_text(self, graph: str, text_output_path_str: str, image_format: Optional[str], is_error_fallback: bool) -> None:
        """Helper to save the puml text file."""
        text_output_file = Path(text_output_path_str)
        try:
            with open(text_output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            if not is_error_fallback:
                self.logger.info(f"PlantUML diagram text saved to {text_output_file}")
            else: 
                 self.logger.info(f"PlantUML diagram text (fallback due to rendering error/missing dependency) saved to {text_output_file}")
        except IOError as e:
            self.logger.error(f"Failed to save PlantUML diagram text to {text_output_file}: {e}")


class PlantUMLLocalActivityDiagram(PlantUMLLocalSaveMixin, PlantUMLActivityDiagram):
    """
    Generates PlantUML activity diagrams locally.
    Inherits 'generate' from PlantUMLActivityDiagram (which uses LLM for PUML syntax generation)
    and 'save' from PlantUMLLocalSaveMixin (which uses local JAR for rendering).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger 

class PlantUMLLocalClassDiagram(PlantUMLLocalSaveMixin, PlantUMLClassDiagram):
    """
    Generates PlantUML class diagrams locally.
    Inherits 'generate' from PlantUMLClassDiagram (which uses LLM for PUML syntax generation)
    and 'save' from PlantUMLLocalSaveMixin (which uses local JAR for rendering).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger
