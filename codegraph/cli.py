"""
-------------------------------
DeepCodeGraph CLI
-------------------------------

This module provides the command-line interface for the DeepCodeGraph tool.
"""

import os
import sys
import argparse
import json
import logging
from typing import Optional, Dict, Any  # Updated import

from codegraph.llm.provider import LLMProvider, LLMProviderFactory
from codegraph.prompts.loader import PromptManager
from codegraph.scanner.repo_scan import RepositoryScanner
from codegraph.graphs.plantuml import PlantUMLActivityDiagram, PlantUMLClassDiagram
from codegraph.graphs.mermaid import MermaidDiagram
from codegraph.graphs.graphviz import GraphvizDiagram
from codegraph.graphs.d2 import D2Diagram
from codegraph.graphs.plantuml_local import PlantUMLLocalActivityDiagram, PlantUMLLocalClassDiagram


def setup_logging(verbosity: int) -> None:
    """
    Configure logging based on verbosity level.

    Args:
        verbosity: Integer representing verbosity level (0-3)
    """
    log_levels = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
        3: logging.DEBUG,
    }
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=log_levels.get(verbosity, logging.INFO), format=log_format
    )
    if verbosity >= 3:
        # Enable detailed debug logging for HTTP requests in verbose mode
        logging.getLogger("urllib3").setLevel(logging.DEBUG)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="DeepCodeGraph: Analyze code repositories and generate dependency graphs"
    )

    # Common options
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times)",
    )
    parser.add_argument(
        "--api-key",
        help="LLM API key (or set the CODEGRAPH_API_KEY env var or your provider's LiteLLM environment variables)",
    )
    parser.add_argument(
        "--provider", help="LLM provider to use (default: gemini)")
    parser.add_argument(
        "--model",
        help="Specific model to use with the provider (default: gemini-2.0-flash-exp)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Graph command
    scan_parser = subparsers.add_parser("graph", help="Visualize a repository")
    scan_source = scan_parser.add_mutually_exclusive_group(required=True)
    scan_source.add_argument(
        "--github",
        type=str,
        metavar="URL",
        help="GitHub repository URL to clone and scan",
    )
    scan_source.add_argument(
        "--path", type=str, metavar="PATH", help="Local directory path to scan"
    )
    scan_parser.add_argument(
        "--extensions",
        type=str,
        default=".py,.js,.java,.cpp,.c,.h",
        help="Comma-separated list of file extensions to scan (default: .py,.js,.java,.cpp,.c,.h)",
    )
    scan_parser.add_argument(
        "--format",  # Renamed from --output-format
        type=str,
        choices=["plantuml", "mermaid", "graphviz", "d2"],  # Updated choices
        default="plantuml",  # Updated default
        help="Main diagram format/language to generate.",  # Updated help
    )
    scan_parser.add_argument(
        "--diagram-type",
        type=str,
        choices=["class", "activity"],
        default="class",
        help="Type of diagram to generate (e.g., class structure or activity flow). Applies to all formats. Default: class."
    )
    scan_parser.add_argument(
        "--image-format",
        type=str,
        choices=["png", "svg"],
        default="png",
        # Purpose: Defines the output file format for the rendered image (if image generation is supported).
        help="Format for the output image (e.g., png, svg). Relevant for diagram types that support local rendering to an image.",
    )
    scan_parser.add_argument(
        "--output",
        type=str,
        default="./",
        help="Directory to save generated graphs (default: current directory)",
    )
    scan_parser.add_argument(
        "--plantuml-service",
        type=str,
        choices=["local", "web"],
        default="local",
        # Purpose: Allows choosing between local PlantUML rendering (requires a JAR) and using the public web service.
        help="PlantUML service to use. 'local' requires a PlantUML JAR for local rendering; 'web' uses the public PlantUML server.",
    )
    scan_parser.add_argument(  # Added for graph command
        "--input-db",
        type=str,
        metavar="FILEPATH.JSON",
        default=None,
        # Purpose: Allows the graph command to use a previously exported JSON DB for incremental scanning.
        # This can speed up processing by only analyzing changed or new files.
        help="Optional path to an existing DB JSON file to use for incremental scanning and caching."
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export", help="Export repository structure")
    export_source = export_parser.add_mutually_exclusive_group(required=True)
    export_source.add_argument(
        "--github",
        type=str,
        metavar="URL",
        help="GitHub repository URL to clone and scan",
    )
    export_source.add_argument(
        "--path", type=str, metavar="PATH", help="Local directory path to scan"
    )
    export_parser.add_argument(
        "--extensions",
        type=str,
        default=".py,.js,.java,.cpp,.c,.h",
        help="Comma-separated list of file extensions to scan (default: .py,.js,.java,.cpp,.c,.h)",
    )
    export_parser.add_argument(
        "--format",
        type=str,
        choices=["json"],
        default="json",
        help="Export format (default: json)",
    )
    export_parser.add_argument(
        "--output", type=str, required=True, help="Output file path"
    )
    export_parser.add_argument(
        "--input-db",
        type=str,
        metavar="FILEPATH.JSON",
        default=None,  # Explicitly None if not provided
        # Purpose: Allows the export command to load an existing JSON DB, perform an incremental scan,
        # and then output the updated DB. This avoids re-analyzing unchanged files.
        help="Optional path to an existing DB JSON file. If provided, the export will update this DB."
    )

    return parser.parse_args()


def get_api_key(args: argparse.Namespace) -> Optional[str]:
    """
    Get the API key from either command line arguments or environment variables.

    Args:
        args: Parsed command line arguments

    Returns:
        API key string or None if not found

    Raises:
        SystemExit: If no API key is found
    """
    api_key = args.api_key or os.environ.get("CODEGRAPH_API_KEY")
    if not api_key and not os.environ.get("CODEGRAPH_CUSTOM_API_ENV") == "1":
        logging.error(
            "Error: No API key provided. Use --api-key or set CODEGRAPH_API_KEY environment variable."
        )
        sys.exit(1)
    return api_key


def get_provider(args: argparse.Namespace) -> Optional[str]:
    """
    Get the API provider from either command line arguments or environment variables.

    Args:
        args: Parsed command line arguments

    Returns:
        LLM Provider string or None if not found

    Raises:
        SystemExit: If no API key is found
    """
    get_provider = args.provider or os.environ.get("CODEGRAPH_LLM_PROVIDER")
    if not get_provider:
        logging.error(
            "Error: No LLM provider specified. Use --provider or set CODEGRAPH_LLM_PROVIDER environment variable."
        )
        sys.exit(1)
    return get_provider


def get_model(args: argparse.Namespace) -> Optional[str]:
    """
    Get the LLM model from either command line arguments or environment variables.

    Args:
        args: Parsed command line arguments

    Returns:
        LLM model string or None if not found

    Raises:
        SystemExit: If no API key is found
    """
    model = args.model or os.environ.get("CODEGRAPH_LLM_MODEL")
    if not model:
        logging.error(
            "Error: No LLM model specified. Use --model or set CODEGRAPH_LLM_MODEL environment variable."
        )
        sys.exit(1)
    return model


def handle_scan_command(scanner: RepositoryScanner, args: argparse.Namespace, existing_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Perform the repository scan, potentially using existing data for caching.

    This function is called by both `graph` and `export` command handlers.
    It populates the `scanner` instance with data from the specified repository path or GitHub URL.
    If `existing_data` (a previously exported JSON structure) is provided, the scanner
    will use it to perform an incremental scan, only analyzing new or changed files.

    Args:
        scanner: The `RepositoryScanner` instance to use for scanning.
        args: Parsed command line arguments, providing repository source (path/github) and extensions.
        existing_data: Optional. A dictionary representing a previously exported repository structure.
                       If provided, enables incremental scanning.
    """
    extensions = tuple(args.extensions.split(","))
    logging.info(f"Scanning with extensions: {extensions}")

    if args.github:
        logging.info(f"Scanning GitHub repository: {args.github}")
        scanner.scan_github_repo(
            args.github, extensions=extensions, existing_data=existing_data)
    elif args.path:
        logging.info(f"Scanning local directory: {args.path}")
        scanner.scan_codebase(
            args.path, extensions=extensions, existing_data=existing_data)


def handle_graph_command(
    scanner: RepositoryScanner, provider: LLMProvider, args: argparse.Namespace, existing_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Handle the 'graph' command to generate diagrams.

    Args:
        scanner: Repository scanner instance
        args: Parsed command line arguments
    """
    os.makedirs(args.output, exist_ok=True)
    generator = None
    # --- Graph Generator Selection ---
    # This section determines which graph generator class to use based on the
    # user-specified '--format', '--diagram-type', and for PlantUML, '--plantuml-service'.

    if args.format == "plantuml":
        if args.plantuml_service == "local":
            if args.diagram_type == "class":
                logging.info("Generating local PlantUML class diagram.")
                generator = PlantUMLLocalClassDiagram(provider)
            elif args.diagram_type == "activity":
                logging.info("Generating local PlantUML activity diagram.")
                generator = PlantUMLLocalActivityDiagram(provider)
        else:  # args.plantuml_service == "web"
            if args.diagram_type == "class":
                logging.info("Generating web-based PlantUML class diagram.")
                generator = PlantUMLClassDiagram(provider)
            elif args.diagram_type == "activity":
                logging.info("Generating web-based PlantUML activity diagram.")
                generator = PlantUMLActivityDiagram(provider)
    elif args.format == "mermaid":
        logging.info(f"Generating Mermaid {args.diagram_type} diagram.")
        generator = MermaidDiagram(provider, diagram_type=args.diagram_type)
    elif args.format == "graphviz":
        logging.info(f"Generating Graphviz {args.diagram_type} diagram.")
        generator = GraphvizDiagram(provider, diagram_type=args.diagram_type)
    elif args.format == "d2":
        logging.info(f"Generating D2 {args.diagram_type} diagram.")
        generator = D2Diagram(provider, diagram_type=args.diagram_type)
    else:
        # Fallback for unsupported graph formats (though argparse choices should prevent this).
        logging.error(f"Unsupported graph format: {args.format}")
        return

    if generator:
        scanner.generate_graph(generator, args.output,
                               image_format=args.image_format, existing_data=existing_data)


def handle_export_command(scanner: RepositoryScanner, args: argparse.Namespace) -> None:
    """
    Handle the 'export' command to export repository structure.

    Args:
        scanner: Repository scanner instance
        args: Parsed command line arguments for the 'export' command.
    """
    existing_data: Optional[Dict[str, Any]] = None
    # --- Load Existing DB for Export Update ---
    # If --input-db is provided, load the JSON file. This data will be passed to
    # scan_codebase/scan_github_repo for incremental processing.
    # Errors during loading (file not found, JSON decode error) are logged, and
    # `existing_data` remains None, leading to a full scan.
    if args.input_db:
        try:
            with open(args.input_db, 'r', encoding='utf-8') as f_db:
                existing_data = json.load(f_db)
                existing_data = existing_data["files"]
            logging.info(
                f"Loaded existing DB from {args.input_db} for export update.")
        except FileNotFoundError:
            logging.warning(
                f"Input DB file {args.input_db} not found for export. Proceeding with a full scan.")
        except json.JSONDecodeError:
            logging.error(
                f"Error decoding JSON from input DB {args.input_db} for export. Proceeding with a full scan.")
            existing_data = None
        except Exception as e:
            logging.error(
                f"Failed to load input DB {args.input_db} for export: {e}. Proceeding with a full scan.")
            existing_data = None

    # Perform the scan. If `existing_data` was loaded, this will be an incremental scan.
    # The `scanner` object will be populated with the (potentially updated) repository structure.
    handle_scan_command(scanner, args, existing_data=existing_data)

    # Export the (potentially updated) repository structure from the scanner.
    logging.info(f"Exporting repository structure to {args.output}")
    repo_structure = scanner.export_repository_structure()

    if args.format == "json":  # args.format here refers to the export_parser's format argument
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(repo_structure, f, indent=2)
        logging.info(f"Repository structure exported to {args.output}")
    else:
        logging.error(
            f"Unsupported export format: {args.format}. Only JSON is currently supported for export.")


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        args = parse_args()
        setup_logging(args.verbose)

        api_key = get_api_key(args)
        provider = get_provider(args)
        model = get_model(args)

        logging.info(f"Initializing scanner with provider: {args.provider}")

        full_model_name = f"{provider}/{model}"

        provider = LLMProviderFactory.create_provider(
            full_model_name, api_key, max_retries=2, retry_delay=5, temperature=0.7
        )

        prompt_manager = PromptManager()

        scanner = RepositoryScanner(
            llm_provider=provider,
            prompt_loader=prompt_manager,
        )

        # Handle commands
        if args.command == "graph":
            existing_files: Optional[Dict[str, Any]] = None
            existing_dep: Optional[Dict[str, Any]] = None
            existing_full: Optional[Dict[str, Any]] = None
            # --- Load Existing DB for Graph Command (Caching) ---
            # If --input-db is provided for the 'graph' command, attempt to load it.
            # This data enables incremental scanning, where only new or changed files are analyzed by the LLM.
            if args.input_db:
                try:
                    with open(args.input_db, 'r', encoding='utf-8') as f_db:
                        existing_full = json.load(f_db)
                        existing_dep = existing_full["dependency_graph"]
                        existing_files = existing_full["files"]

                    logging.info(
                        f"Loaded existing DB for graph command from {args.input_db}")
                except FileNotFoundError:
                    logging.warning(
                        f"Input DB file {args.input_db} not found for graph command. Proceeding with a full scan.")
                except json.JSONDecodeError:
                    logging.error(
                        f"Error decoding JSON from input DB {args.input_db} for graph command. Proceeding with a full scan.")
                    existing_files = None
                except Exception as e:
                    logging.error(
                        f"Failed to load input DB {args.input_db} for graph command: {e}. Proceeding with a full scan.")
                    existing_files = None

            # Perform the scan, using `existing_data_for_graph` if it was loaded.
            # The `scanner` instance will be populated, and `scanner.actual_llm_scans_performed` will be set.
            handle_scan_command(
                scanner, args, existing_data=existing_files)

            # --- No-Change Detection for Graph Command ---
            # If an input DB was provided (`args.input_db` is not None) AND
            # the scanner indicates that no actual LLM scans were performed in this run
            # (meaning all relevant files were found in the cache and were unchanged),
            # then graph generation can be skipped to save time and resources.
            if args.input_db and not scanner.actual_llm_scans_performed:
                print(
                    "No relevant file changes detected since the last scan.")
            # Otherwise (full scan or changes detected), proceed to generate the graph.
            handle_graph_command(scanner, provider, args,
                                 existing_data=existing_full)
        elif args.command == "export":
            # For the 'export' command, `handle_scan_command` (which handles `existing_data` loading)
            # is called *within* `handle_export_command`.
            # to allow existing_data to be loaded first.
            handle_export_command(scanner, args)
        else:
            print("No command specified. Use -h for help.")
            sys.exit(1)

    except FileNotFoundError as e:
        # print(f"Error: {e}")
        logging.error(f"File not found: {e}")
        sys.exit(1)
    except ValueError as e:
        # print(f"Error: {e}")
        logging.error(f"Invalid input: {e}")
        sys.exit(1)
    except RuntimeError as e:
        # print(f"Error: {e}")
        logging.error(f"Runtime error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        # print("\nOperation cancelled by user.")
        logging.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        # print(f"Unexpected error: {e}")
        logging.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
