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
from typing import Optional

from codegraph.llm.provider import LLMProvider, LLMProviderFactory
from codegraph.prompts.loader import PromptManager
from codegraph.scanner.repo_scan import RepositoryScanner
from codegraph.graphs.plantuml import PlantUMLActivityDiagram, PlantUMLClassDiagram


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
    parser.add_argument("--provider", help="LLM provider to use (default: gemini)")
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
        "--type",
        type=str,
        choices=["plantuml", "uml-class", "all"],
        default="all",
        help="Type of graph to generate (default: all)",
    )
    scan_parser.add_argument(
        "--output",
        type=str,
        default="./",
        help="Directory to save generated graphs (default: current directory)",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export repository structure")
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


def handle_scan_command(scanner: RepositoryScanner, args: argparse.Namespace) -> None:
    """
    Handle the 'scan' command to analyze a code repository.

    Args:
        scanner: Repository scanner instance
        args: Parsed command line arguments
    """
    extensions = tuple(args.extensions.split(","))
    logging.info(f"Scanning with extensions: {extensions}")

    if args.github:
        logging.info(f"Scanning GitHub repository: {args.github}")
        scanner.scan_github_repo(args.github, extensions=extensions)
    elif args.path:
        logging.info(f"Scanning local directory: {args.path}")
        scanner.scan_codebase(args.path, extensions=extensions)


def handle_graph_command(
    scanner: RepositoryScanner, provider: LLMProvider, args: argparse.Namespace
) -> None:
    """
    Handle the 'graph' command to generate diagrams.

    Args:
        scanner: Repository scanner instance
        args: Parsed command line arguments
    """
    os.makedirs(args.output, exist_ok=True)

    if args.type in ["activity", "all"]:
        logging.info("Generating PlantUML activity diagram")
        plantuml_generator = PlantUMLActivityDiagram(provider)
        print(scanner.generate_graph(plantuml_generator, args.output))

    if args.type in ["uml", "all"]:
        logging.info("Generating PlantUML class diagram")
        plantuml_generator = PlantUMLClassDiagram(provider)
        print(scanner.generate_graph(plantuml_generator, args.output))


def handle_export_command(scanner: RepositoryScanner, args: argparse.Namespace) -> None:
    """
    Handle the 'export' command to export repository structure.

    Args:
        scanner: Repository scanner instance
        args: Parsed command line arguments
    """
    logging.info(f"Exporting repository structure to {args.output}")
    repo_structure = scanner.export_repository_structure()

    if args.format == "json":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(repo_structure, f, indent=2)
        logging.info(f"Repository structure exported to {args.output}")


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
            handle_scan_command(scanner, args)
            handle_graph_command(scanner, provider, args)
        elif args.command == "export":
            handle_scan_command(scanner, args)
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
