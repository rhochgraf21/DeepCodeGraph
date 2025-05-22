"""
-------------------------------
Repository Scanner
-------------------------------

This module provides the RepositoryScanner class, which is responsible for analyzing
code repositories and generating a dependency graph.
"""
import os
from pathlib import Path
import tempfile
import subprocess
from typing import Dict, List, Tuple, Optional, Any, Protocol, Union  # Added Union
import json
import logging

from codegraph.domain.model import File, Function, Method, Class, Global, CodeElement
from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.graphs.base import GraphGenerator
from codegraph.utils.helpers import calculate_file_hash


class RepositoryScanner:
    """
    Scans and analyzes a code repository.

    This class is responsible for:
    - Accepting a local directory or GitHub URL for scanning
    - Analyzing code files using an LLM
    - Resolving dependencies between functions and methods
    - Building a complete dependency graph of the codebase

    Attributes:
        files (Dict[str, File]): Dictionary mapping filenames to File objects
        functions_map (Dict[str, Dict[str, Function]]): Map of function names to files they appear in
        methods_map (Dict[str, Method]): Map of "Class.method" names to Method objects
        classes_map (Dict[str, Class]): Map of class names to Class objects
        actual_llm_scans_performed (bool): Flag to indicate if any file required fresh LLM analysis.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_loader: PromptManager,
        token_limit: int = 128000,
        fallback_threshold: float = 0.9,
    ):
        """
        Initialize the repository scanner.

        Args:
            llm_provider: Provider for LLM queries
            prompt_loader: Loader for prompt templates
            token_limit: Maximum token limit for LLM queries
            fallback_threshold: Threshold for fallback strategies (0.0 - 1.0)
        """
        self.files: Dict[str, File] = {}
        self.functions_map: Dict[
            str, Dict[str, Function]
        ] = {}
        self.methods_map: Dict[str, Method] = {}
        self.classes_map: Dict[str, Class] = {}
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold
        self.llm = llm_provider
        self.prompts = prompt_loader
        self.logger = logging.getLogger(__name__)
        # self.actual_llm_scans_performed: Flag to track if any file was truly analyzed by LLM
        # in the current scan, as opposed to being loaded from cache.
        # Reset in scan_codebase, set to True in insert.
        self.actual_llm_scans_performed = False

    def insert(self, code: str, relative_fpath: str, current_file_hash: str) -> None:
        """
        Analyze a code file using the LLM and insert its structure into the repository.
        This method is called when a file is new or its content has changed.

        Args:
            code: Source code content of the file.
            relative_fpath: Relative path of the file from the repository root.
            current_file_hash: SHA256 hash of the current file content.
        """
        print(f"Inserting file: {relative_fpath}")
        self.logger.info(
            f"Analyzing {relative_fpath} (hash: {current_file_hash}) with LLM.")
        analysis_prompt = self.prompts.format_prompt(
            "code_analysis", code=code)
        try:
            analysis_json = self.llm.query(analysis_prompt)
            analysis = self._extract_json_from_response(analysis_json)

            file_obj = File(
                name=relative_fpath,
                description=analysis.get(
                    "file_description", "No description available"),
                content_hash=current_file_hash,
                raw_code=code,
                imports=analysis.get("imports", [])
            )

            for func_data in analysis.get("functions", []):
                func = Function.from_dict(func_data)
                file_obj.add_function(func)
                if func.name not in self.functions_map:
                    self.functions_map[func.name] = {}
                self.functions_map[func.name][relative_fpath] = func

            for class_data in analysis.get("classes", []):
                cls = Class.from_dict(class_data)
                for method in cls.methods:
                    key = f"{cls.name}.{method.name}"
                    self.methods_map[key] = method
                file_obj.add_class(cls)
                self.classes_map[cls.name] = cls

            for global_data in analysis.get("globals", []):
                glob = Global.from_dict(global_data)
                file_obj.add_global(glob)

            self.files[relative_fpath] = file_obj
            self.actual_llm_scans_performed = True  # Set flag as LLM scan was done
        except Exception as e:
            self.logger.error(
                f"Error processing file {relative_fpath} with LLM: {e}", exc_info=True)

    def scan_codebase(self, path: str, extensions: Tuple[str, ...], existing_data: Optional[Dict[str, Any]] = None) -> None:
        scan_path = Path(path).resolve()
        if not scan_path.exists():
            raise FileNotFoundError(f"Path does not exist: {scan_path}")
        if not scan_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {scan_path}")

        # Reset instance maps and scan flag at the beginning of each scan operation.
        # This ensures that each call to scan_codebase starts with a clean state for the scanner instance,
        # populating its internal data structures (`self.files`, `self.functions_map`, etc.) based on
        # the current scan, potentially using `existing_data` for caching.
        self.files.clear()
        self.functions_map.clear()
        self.methods_map.clear()
        self.classes_map.clear()
        # self.actual_llm_scans_performed is reset to False. It will be set to True in `self.insert`
        # if any file requires fresh analysis by the LLM. This helps the CLI determine if a graph
        # generation step can be skipped if no files were changed.
        self.actual_llm_scans_performed = False

        # processed_db_paths keeps track of file paths from existing_data that are
        # still present in the current codebase (either matched by hash or re-scanned).
        # Used later to identify files that were deleted since the last scan.
        processed_db_paths = set()
        self.logger.info(
            f"Starting codebase scan at {scan_path} for extensions: {extensions}")

        for root, _, files_in_dir in os.walk(scan_path):
            for fname in files_in_dir:
                fpath = Path(root) / fname
                if not fpath.is_file() or not str(fname).endswith(tuple(extensions)):
                    continue

                relative_fpath = str(fpath.relative_to(scan_path))

                try:
                    # Calculate current hash of the file content.
                    # `calculate_file_hash` (from utils.helpers) reads the file and computes a hash (default SHA256).
                    current_hash = calculate_file_hash(fpath)
                    # Caching Logic:
                    # If `existing_data` (loaded from a previous scan's JSON DB) is provided,
                    # and the current file (`relative_fpath`) exists in `existing_data`,
                    # and its stored content_hash matches `current_hash`, then it's a cache hit.
                    if existing_data and \
                       relative_fpath in existing_data and \
                       isinstance(existing_data.get(relative_fpath), dict) and \
                       existing_data[relative_fpath].get('content_hash') == current_hash:

                        # print(f"No need to update {relative_fpath}")

                        self.logger.info(
                            f"Cache hit for {relative_fpath}. Loading from existing data.")
                        # Reconstruct the File object and its contained elements (functions, classes, etc.)
                        # from the dictionary representation stored in `existing_data`.
                        # `File.from_dict` is responsible for this deserialization.
                        file_data_dict = existing_data[relative_fpath]
                        file_obj = File.from_dict(file_data_dict)

                        # Populate the scanner's internal maps with the data from the cached file.
                        self.files[relative_fpath] = file_obj
                        for func in file_obj.functions:
                            if func.name not in self.functions_map:
                                self.functions_map[func.name] = {}
                            self.functions_map[func.name][relative_fpath] = func
                        for cls in file_obj.classes:
                            self.classes_map[cls.name] = cls
                            for method in cls.methods:
                                self.methods_map[f"{cls.name}.{method.name}"] = method

                        # Mark this path as processed.
                        processed_db_paths.add(relative_fpath)
                    # Cache miss (file changed, or hash field missing/mismatched) or new file.
                    else:
                        if existing_data and relative_fpath in existing_data:
                            self.logger.info(
                                f"Cache miss for {relative_fpath} (hash mismatch or different). Re-scanning with LLM.")
                        else:
                            self.logger.info(
                                f"New file {relative_fpath}. Scanning with LLM.")

                        # Read file content and call `self.insert` for LLM-based analysis.
                        # `self.insert` will set `self.actual_llm_scans_performed = True`.
                        with open(fpath, "r", encoding="utf-8") as f_content:
                            code = f_content.read()
                        self.insert(code, relative_fpath, current_hash)
                        if existing_data and relative_fpath in existing_data:
                            # Mark as processed even if re-scanned.
                            processed_db_paths.add(relative_fpath)

                except FileNotFoundError:
                    self.logger.warning(
                        f"File {relative_fpath} not found during processing. Skipping.")
                except Exception as e:
                    self.logger.error(
                        f"Failed to process or hash {relative_fpath}: {e}", exc_info=True)

        # Handling of deleted files:
        # If `existing_data` was provided, compare its keys (file paths) with the paths
        # of files actually found and processed in the current scan (`self.files.keys()`).
        # Files in `existing_data` but not in `self.files` are considered deleted.
        if existing_data:
            deleted_files = set(existing_data.keys()) - set(self.files.keys())
            for deleted_fpath in deleted_files:
                self.logger.info(
                    f"File {deleted_fpath} present in DB but not in current scan (deleted). It will not be included in the output structure.")
                # No explicit removal from `self.files` is needed because `self.files` was cleared
                # at the start and only populated with currently existing/processed files.

        self.logger.info(
            f"Finished scanning. Total files processed into structure: {len(self.files)}. LLM scans performed in this run: {self.actual_llm_scans_performed}")

    def scan_github_repo(
        # Removed default extensions from here
        self, github_url: str, extensions: Tuple[str, ...],
        existing_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Clone a GitHub repository and scan its code.
        The extensions default is now handled by the caller (e.g. CLI)
        """
        # actual_llm_scans_performed is reset by scan_codebase, so no need to do it here.
        repo_path = self._clone_github_repo(github_url)
        self.logger.info(f"Cloned repository to {repo_path}. Now scanning...")
        self.scan_codebase(repo_path, extensions=extensions,
                           existing_data=existing_data)

    def resolve_imports(self, filename: str) -> Dict[str, List[str]]:
        """
        Resolve imported functions for a file.

        Args:
            filename: Name of the file

        Returns:
            Dictionary mapping function names to the files they're imported from
        """
        if filename not in self.files:
            return {}
        file_obj = self.files[filename]
        imported_functions = {}
        for imp in file_obj.imports:
            if imp in self.files:
                imp_file = self.files[imp]
                for func in imp_file.functions:
                    imported_functions.setdefault(func.name, []).append(imp)
        return imported_functions

    def resolve(self, function_name: str, from_file: str = None) -> List[Dict]:
        """
        Resolve a function's dependencies.

        Args:
            function_name: Name of the function to resolve
            from_file: File where the function call originates

        Returns:
            List of resolved dependencies
        """
        if "." in function_name:
            method = self.methods_map.get(function_name)
            if method:
                return self._resolve_dependencies(method, from_file)

        if function_name in self.functions_map:
            if from_file and from_file in self.functions_map[function_name]:
                func = self.functions_map[function_name][from_file]
                return self._resolve_dependencies(func, from_file)
            elif len(self.functions_map[function_name]) == 1:
                file_, func = next(
                    iter(self.functions_map[function_name].items()))
                return self._resolve_dependencies(func, file_)
            else:
                function_options = list(
                    self.functions_map[function_name].items())
                return self._resolve_ambiguous_function(function_name, function_options, from_file)
        return [{"error": f"Function or method {function_name} not found in the repository"}]

    def _resolve_ambiguous_function(
        self,
        function_name: str,
        function_options: List[Tuple[str, Function]],
        from_file: str = None,
    ) -> List[Dict]:
        if from_file:
            file_obj = self.files.get(from_file)
            if file_obj:
                for file_path_key, func_obj in function_options:
                    if file_path_key in file_obj.imports:
                        self.logger.info(
                            f"Ambiguity for {function_name} resolved: using version from imported file {file_path_key}")
                        return self._resolve_dependencies(func_obj, file_path_key)

        self.logger.info(
            f"Ambiguity for {function_name} requires LLM resolution.")
        options_descriptions = []
        for file, func in function_options:
            options_descriptions.append(
                {
                    "file": file,
                    "function_name": func.name,
                    "description": func.description,
                    "called_functions": func.called_functions,
                    "parameters": func.parameters,
                    "return_type": func.return_type,
                }
            )

        context = ""
        if from_file:
            file_obj = self.files.get(from_file)
            if file_obj:
                context = f"""
                The function '{function_name}' is being called from file '{from_file}'.
                Calling file description: {file_obj.description}
                Imports: {file_obj.imports}
                """

        ambiguity_prompt = self.prompts.format_prompt(
            "dependency_resolution",
            function_name=function_name,
            context=context,
            implementations=json.dumps(options_descriptions, indent=2),
        )

        try:
            resolution_json = self.llm.query(ambiguity_prompt)
            resolution = self._extract_json_from_response(resolution_json)
            likely_file = resolution.get("file")
            if likely_file and likely_file in self.functions_map[function_name]:
                func = self.functions_map[function_name][likely_file]
                return self._resolve_dependencies(func, likely_file)
            else:
                self.logger.warning(
                    f"LLM resolution for {function_name} failed or pointed to non-existent file. Falling back to first option.")
                file, func = function_options[0]
                return self._resolve_dependencies(func, file)
        except Exception as e:
            self.logger.error(
                f"Error resolving ambiguous function {function_name} with LLM: {e}", exc_info=True)
            file, func = function_options[0]
            return self._resolve_dependencies(func, file)

    def _resolve_dependencies(
        self, element: Union[Function, Method], from_file_path: str = None
    ) -> List[Dict]:
        if element.resolved_dependencies:
            return [
                dep.to_dict() if hasattr(dep, "to_dict") else dep
                for dep in element.resolved_dependencies
            ]

        resolved_deps = []
        imports_context_file = from_file_path
        imported_functions_map = self.resolve_imports(
            imports_context_file) if imports_context_file else {}

        for called_name in element.called_functions:
            resolved_dep_obj = None
            if isinstance(element, Method):
                potential_method_key = f"{element.class_name}.{called_name}"
                if potential_method_key in self.methods_map:
                    resolved_dep_obj = self.methods_map[potential_method_key]

            if not resolved_dep_obj and "." in called_name:
                if called_name in self.methods_map:
                    resolved_dep_obj = self.methods_map[called_name]

            if not resolved_dep_obj and called_name in self.functions_map:
                if called_name in imported_functions_map and imported_functions_map[called_name]:
                    imported_file_path = imported_functions_map[called_name][0]
                    if imported_file_path in self.functions_map[called_name]:
                        resolved_dep_obj = self.functions_map[called_name][imported_file_path]
                elif imports_context_file and imports_context_file in self.functions_map[called_name]:
                    resolved_dep_obj = self.functions_map[called_name][imports_context_file]
                elif len(self.functions_map[called_name]) == 1:
                    resolved_dep_obj = next(
                        iter(self.functions_map[called_name].values()))
                else:
                    self.logger.warning(
                        f"Ambiguous call to {called_name} from {element.qualified_name}. LLM resolution might be needed if not resolved by context.")
                    pass

            if resolved_dep_obj:
                resolved_deps.append(resolved_dep_obj)
            else:
                self.logger.info(
                    f"'{called_name}' called by '{element.qualified_name}' not found directly. Attempting inference.")
                inference_prompt = self.prompts.format_prompt(
                    "function_inference",
                    called_func=called_name,
                    function_name=element.name,
                    from_file=imports_context_file if imports_context_file else "unknown",
                )
                try:
                    inference_json = self.llm.query(inference_prompt)
                    inference = self._extract_json_from_response(
                        inference_json)
                    inferred_func = Function.from_dict(inference)
                    inferred_func.is_inferred = True
                    inferred_func.qualified_name = f"inferred:{called_name}"
                    resolved_deps.append(inferred_func)
                except Exception as e:
                    self.logger.error(
                        f"Error inferring function {called_name}: {e}", exc_info=True)
                    placeholder = Function(
                        name=called_name, description="Unknown external or unresolvable function")
                    placeholder.is_inferred = True
                    placeholder.qualified_name = f"unknown:{called_name}"
                    resolved_deps.append(placeholder)

        element.resolved_dependencies = resolved_deps
        return [
            dep.to_dict() if hasattr(dep, "to_dict") else dep for dep in resolved_deps
        ]

    def get_dependency_graph(self) -> Dict:
        graph = {}
        for file_path in self.files.keys():  # Iterate over files that are currently part of the scan
            # Process functions in this file
            for func_name, func_map_for_file_path in self.functions_map.items():
                if file_path in func_map_for_file_path:  # Check if the function belongs to the current file
                    func_obj = func_map_for_file_path[file_path]
                    if not func_obj.resolved_dependencies:
                        self._resolve_dependencies(func_obj, file_path)
                    graph[func_obj.qualified_name] = [
                        dep.qualified_name if hasattr(
                            dep, "qualified_name") else str(dep)
                        for dep in func_obj.resolved_dependencies
                    ]

        for method_key, method_obj in self.methods_map.items():
            class_obj = self.classes_map.get(method_obj.class_name)
            method_file_path = None
            if class_obj:  # Find which file this method belongs to
                for f_path, file_data in self.files.items():
                    if class_obj.name in [c.name for c in file_data.classes]:
                        method_file_path = f_path
                        break

            if not method_obj.resolved_dependencies:
                self._resolve_dependencies(method_obj, method_file_path)
            graph[method_obj.qualified_name] = [
                dep.qualified_name if hasattr(
                    dep, "qualified_name") else str(dep)
                for dep in method_obj.resolved_dependencies
            ]
        return graph

    def export_repository_structure(self) -> Dict:
        # self.get_dependency_graph()

        return {
            "files": {
                name: file_obj.to_dict() for name, file_obj in self.files.items()
            },
            "dependency_graph": self.get_dependency_graph(),
        }

    def generate_graph(self, graph_generator: GraphGenerator, file_path: str, image_format: Optional[str] = None, existing_data: Optional[Dict[str, Any]] = None) -> str:
        repo_structure = self.export_repository_structure(
        ) if not existing_data else existing_data
        code = graph_generator.generate(repository_data=repo_structure)
        graph_generator.save(code, file_path, image_format=image_format)

    def _clone_github_repo(self, github_url: str) -> str:
        temp_dir = tempfile.mkdtemp(prefix="repo_")
        cmd = ["git", "clone", github_url, temp_dir]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info(f"Successfully cloned {github_url} to {temp_dir}")
        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Failed to clone {github_url}. Error: {e.stderr}")
            raise
        return temp_dir

    def _extract_json_from_response(self, response: str) -> Dict:
        import re
        import json

        match = re.search(r"```json\n(.*?)\n```", response,
                          re.DOTALL | re.IGNORECASE)
        if match:
            json_str = match.group(1)
        else:
            match_curly = re.search(r"({[\s\S]*})", response)
            if match_curly:
                json_str = match_curly.group(1)
            else:
                json_str = response

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Error decoding JSON: {e}. Raw response part considered JSON: '{json_str[:200]}...'")
            raise
