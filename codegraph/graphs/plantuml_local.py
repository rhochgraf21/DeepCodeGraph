import logging
from pathlib import Path
from typing import Optional
import os # For checking environment variable for JAR path

# Attempt to import pythonplantuml, handle if not found
try:
    from pythonplantuml import generate_uml_png, generate_uml_svg
    PYTHONPLANTRUML_AVAILABLE = True
except ImportError:
    PYTHONPLANTRUML_AVAILABLE = False

from codegraph.graphs.plantuml import PlantUMLActivityDiagram, PlantUMLClassDiagram
from codegraph.utils.helpers import create_directory_if_not_exists, sanitize_filename
from datetime import datetime # For timestamp in filename if needed

logger = logging.getLogger(__name__)

# --- Module-Level Comments ---
# This module provides functionality for generating PlantUML diagrams locally
# using the 'pythonplantuml' library and a local PlantUML JAR file.
# It offers an alternative to the web-based PlantUML generation,
# which can be useful for environments without internet access or for privacy.

# --- PLANTUML_JAR_PATH Logic ---
# Defines the path to the PlantUML JAR file.
# Users can specify a custom path by setting the 'PLANTUML_JAR' environment variable.
# If the environment variable is not set, it defaults to '/usr/local/bin/plantuml.jar'.
# This default path is based on common installation locations for PlantUML.
DEFAULT_PLANTUML_JAR_PATH = "/usr/local/bin/plantuml.jar"
PLANTUML_JAR_PATH = os.environ.get("PLANTUML_JAR", DEFAULT_PLANTUML_JAR_PATH)

class PlantUMLLocalSaveMixin:
    """
    Mixin class to provide local PlantUML saving functionality using pythonplantuml.
    Assumes 'self.logger' is available from the class using this mixin.
    """
    def save(self, graph: str, output_path: str, image_format: Optional[str] = None) -> None:
        if not PYTHONPLANTRUML_AVAILABLE:
            self.logger.error(
                "The 'pythonplantuml' library is not installed. Cannot generate PlantUML diagram locally. "
                "Please install it (e.g., 'pip install pythonplantuml')."
            )
            # Fallback: Save the PlantUML text anyway
            self._save_plantuml_text(graph, output_path, image_format, is_error_fallback=True)
            return

        # Check for PlantUML JAR existence.
        if not Path(PLANTUML_JAR_PATH).is_file():
            self.logger.error(
                f"PlantUML JAR not found at {PLANTUML_JAR_PATH}. Cannot generate PlantUML diagram locally. "
                f"Ensure plantuml.jar is at this location or set PLANTUML_JAR environment variable."
            )
            # Save the .puml text as a fallback if JAR is missing.
            self._save_plantuml_text(graph, output_path, image_format, is_error_fallback=True)
            return

        image_format = (image_format or "png").lower() # Default to png if not specified

        # --- Filename/Path Manipulation Logic ---
        # Determine output file path for the image and the .puml text file.
        output_dir = create_directory_if_not_exists(output_path)
        
        base_filename_stem = "" # Filename without extension.
        specified_output_is_dir = Path(output_path).is_dir()

        if specified_output_is_dir:
            # If output_path is a directory, generate a unique filename using a timestamp.
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base_filename_stem = sanitize_filename(f"dcg-{self.__class__.__name__}-{timestamp}")
            # .puml text file path
            text_output_file = output_dir / f"{base_filename_stem}.puml"
            # Image file path (e.g., .png, .svg)
            image_output_file = output_dir / f"{base_filename_stem}.{image_format}"
        else:
            # If output_path is a specific file path (not a directory).
            p_output_path = Path(output_path)
            create_directory_if_not_exists(str(p_output_path.parent)) # Ensure parent directory exists.
            
            # Case 1: The specified output_path already has the desired image format extension.
            # Example: --output /path/to/diagram.png --image-format png
            if p_output_path.suffix[1:].lower() == image_format:
                base_filename_stem = p_output_path.stem # "diagram"
                image_output_file = p_output_path # /path/to/diagram.png
                # The .puml text file will be saved as /path/to/diagram.puml
                text_output_file = p_output_path.with_suffix(".puml")
            else:
                # Case 2: The specified output_path has a different/no extension, or is intended as a base name.
                # Example: --output /path/to/my_diagram --image-format png -> my_diagram.png, my_diagram.puml
                # Example: --output /path/to/my_diagram.txt --image-format png -> my_diagram.png, my_diagram.puml
                base_filename_stem = p_output_path.stem if p_output_path.suffix else p_output_path.name
                image_output_file = p_output_path.with_suffix(f".{image_format}")
                text_output_file = p_output_path.with_suffix(".puml")

                # If, after suffix manipulation, the text and image files would have the same name
                # (e.g., if image_format was 'puml', or if output_path was 'diag.puml' and image_format was also 'puml'),
                # then adjust the text file name to avoid overwrite by image rendering (if renderer also produces .puml).
                # This is more of a safeguard; pythonplantuml typically generates .png or .svg, not .puml.
                if image_output_file == text_output_file and image_format != "puml": # Check if image_format is not puml
                     text_output_file = image_output_file.parent / (image_output_file.stem + "_text.puml")


        # Save the PlantUML (.puml) text file first. This is always done.
        self._save_plantuml_text(graph, str(text_output_file), image_format, is_error_fallback=False)

        self.logger.info(f"Attempting to render PlantUML diagram locally to {image_output_file} using pythonplantuml...")
        try:
            # --- Calls to generate_uml_png and generate_uml_svg ---
            # These functions from the 'pythonplantuml' library invoke the PlantUML JAR
            # to convert the PlantUML text (graph) into an image.
            # - `graph`: The PlantUML diagram syntax as a string.
            # - `str(image_output_file.parent)`: The directory where the image should be saved.
            # - `PLANTUML_JAR_PATH`: Path to the PlantUML JAR executable.
            # - `filename=image_output_file.stem`: The desired name of the output image file (without extension).
            #   The library will append the correct extension (.png or .svg) based on the function called.
            if image_format == "png":
                generate_uml_png(graph, str(image_output_file.parent), PLANTUML_JAR_PATH, filename=image_output_file.stem)
            elif image_format == "svg":
                generate_uml_svg(graph, str(image_output_file.parent), PLANTUML_JAR_PATH, filename=image_output_file.stem)
            else:
                self.logger.warning(f"Unsupported image format '{image_format}' for local PlantUML generation. Skipping image.")
                return # Do not proceed if format is not supported for local rendering.

            # Verify that the image file was actually created by pythonplantuml.
            if image_output_file.exists():
                self.logger.info(f"PlantUML image successfully saved locally to {image_output_file}")
            else:
                self.logger.error(f"Local PlantUML generation reported success, but output file {image_output_file} not found.")

        except Exception as e:
            self.logger.error(f"An error occurred during local PlantUML image generation: {e}")
            self.logger.info(f"PlantUML text was saved to {text_output_file}")

    def _save_plantuml_text(self, graph: str, text_output_path_str: str, image_format: Optional[str], is_error_fallback: bool) -> None:
        """Helper to save the puml text file."""
        text_output_file = Path(text_output_path_str)
        try:
            with open(text_output_file, "w+", encoding='utf-8') as f:
                f.write(graph)
            if not is_error_fallback:
                self.logger.info(f"PlantUML diagram text saved to {text_output_file}")
            else: # If it's a fallback save due to rendering error
                 self.logger.info(f"PlantUML diagram text (fallback due to rendering error) saved to {text_output_file}")
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
        # Ensure the logger is available in the mixin, especially if base classes don't guarantee it.
        self.logger = logger 

class PlantUMLLocalClassDiagram(PlantUMLLocalSaveMixin, PlantUMLClassDiagram):
    """
    Generates PlantUML class diagrams locally.
    Inherits 'generate' from PlantUMLClassDiagram (which uses LLM for PUML syntax generation)
    and 'save' from PlantUMLLocalSaveMixin (which uses local JAR for rendering).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the logger is available in the mixin.
        self.logger = logger
