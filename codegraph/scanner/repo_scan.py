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
from typing import Dict, List, Tuple, Optional, Any, Protocol
import json

from codegraph.domain.model import File, Function, Method, Class, Global, CodeElement
from codegraph.llm.provider import LLMProvider
from codegraph.prompts.loader import PromptManager
from codegraph.graphs.base import GraphGenerator


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
        ] = {}  # {function_name: {filename: function_obj}}
        self.methods_map: Dict[str, Method] = {}  # { "Class.method": Method }
        self.classes_map: Dict[str, Class] = {}  # { class_name: Class }
        self.token_limit = token_limit
        self.fallback_threshold = fallback_threshold
        self.llm = llm_provider
        self.prompts = prompt_loader

    def insert(self, code: str, filename: str) -> None:
        """
        Analyze a code file using the LLM and insert its structure into the repository.

        Args:
            code: Source code content
            filename: Name of the file
        """
        analysis_prompt = self.prompts.format_prompt("code_analysis", code=code)
        try:
            analysis_json = self.llm.query(analysis_prompt)
            analysis = self._extract_json_from_response(analysis_json)
            file_obj = File(
                filename, analysis.get("file_description", "No description available")
            )
            file_obj.raw_code = code
            file_obj.imports = analysis.get("imports", [])

            # Process functions
            for func_data in analysis.get("functions", []):
                func = Function(
                    func_data["name"],
                    func_data.get("description", "No description available"),
                    func_data.get("called_functions", []),
                    func_data.get("parameters", []),
                    func_data.get("return_type"),
                )
                file_obj.add_function(func)
                if func.name not in self.functions_map:
                    self.functions_map[func.name] = {}
                self.functions_map[func.name][filename] = func

            # Process classes and their methods
            for class_data in analysis.get("classes", []):
                cls = Class(
                    class_data["name"],
                    class_data.get("description", "No description available"),
                )
                for method_data in class_data.get("methods", []):
                    method = Method(
                        method_data["name"],
                        method_data.get("description", "No description available"),
                        cls.name,
                        method_data.get("called_functions", []),
                        method_data.get("parameters", []),
                        method_data.get("return_type"),
                    )
                    cls.add_method(method)
                    key = f"{cls.name}.{method.name}"
                    self.methods_map[key] = method
                file_obj.add_class(cls)
                self.classes_map[cls.name] = cls

            # Process globals
            for global_data in analysis.get("globals", []):
                glob = Global(
                    global_data["name"],
                    global_data.get("description", "No description available"),
                    global_data.get("value"),
                )
                file_obj.add_global(glob)

            self.files[filename] = file_obj
        except Exception as e:
            print(f"Error processing file {filename}: {e}")

    def scan_codebase(
        self, path: str, extensions: Tuple[str, ...] = (".c", ".h", ".cpp", ".py")
    ) -> None:
        """
        Recursively scan a directory for files with given extensions and analyze them.

        Args:
            path: Directory path to scan
            extensions: File extensions to include
        """

        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        for root, _, files in os.walk(path):
            for fname in files:
                if fname.endswith(extensions):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            code = f.read()
                        print(f"Inserting file: {fpath}")
                        self.insert(code, fname)
                    except Exception as e:
                        print(f"Failed to read {fpath}: {e}")

    def scan_github_repo(
        self, github_url: str, extensions: Tuple[str, ...] = (".c", ".h", ".cpp", ".py")
    ) -> None:
        """
        Clone a GitHub repository and scan its code.

        Args:
            github_url: URL of the GitHub repository
        """
        repo_path = self._clone_github_repo(github_url)
        print(f"Cloned repository to {repo_path}. Now scanning...")
        self.scan_codebase(repo_path, extensions=extensions)

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
                file_, func = next(iter(self.functions_map[function_name].items()))
                return self._resolve_dependencies(func, file_)
            else:
                function_options = list(self.functions_map[function_name].items())
                return self._resolve_ambiguous_function(
                    function_name, function_options, from_file
                )
        return [{"error": f"Function {function_name} not found in the repository"}]

    def _resolve_ambiguous_function(
        self,
        function_name: str,
        function_options: List[Tuple[str, Function]],
        from_file: str = None,
    ) -> List[Dict]:
        """
        Resolve a function when multiple implementations exist.

        Args:
            function_name: Name of the function
            function_options: List of (filename, function) tuples
            from_file: File where the function call originates

        Returns:
            List of resolved dependencies
        """
        if from_file:
            imported_functions = self.resolve_imports(from_file)
            for file, func in function_options:
                if file in self.files[from_file].imports:
                    return self._resolve_dependencies(func, file)

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
            file_obj = self.files[from_file]
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
            if likely_file in self.functions_map[function_name]:
                func = self.functions_map[function_name][likely_file]
                return self._resolve_dependencies(func, likely_file)
            else:
                file, func = function_options[0]
                return self._resolve_dependencies(func, file)
        except Exception as e:
            print(f"Error resolving ambiguous function {function_name}: {e}")
            file, func = function_options[0]
            return self._resolve_dependencies(func, file)

    def _resolve_dependencies(
        self, function: Function, from_file: str = None
    ) -> List[Dict]:
        """
        Resolve dependencies for a specific function.

        Args:
            function: Function object
            from_file: File where the function is defined

        Returns:
            List of resolved dependencies
        """
        if function.resolved_dependencies:
            return [
                dep.to_dict() if hasattr(dep, "to_dict") else dep
                for dep in function.resolved_dependencies
            ]

        resolved_deps = []
        imported_functions = self.resolve_imports(from_file) if from_file else {}

        for called_func in function.called_functions:
            if "." in called_func and called_func in self.methods_map:
                resolved_deps.append(self.methods_map[called_func])
                continue

            if called_func in self.functions_map:
                if (
                    called_func in imported_functions
                    and imported_functions[called_func]
                ):
                    for imported_file in imported_functions[called_func]:
                        if imported_file in self.functions_map[called_func]:
                            resolved_deps.append(
                                self.functions_map[called_func][imported_file]
                            )
                            break
                    else:
                        if from_file in self.functions_map[called_func]:
                            resolved_deps.append(
                                self.functions_map[called_func][from_file]
                            )
                        else:
                            file, func = next(
                                iter(self.functions_map[called_func].items())
                            )
                            resolved_deps.append(func)
                else:
                    if from_file in self.functions_map[called_func]:
                        resolved_deps.append(self.functions_map[called_func][from_file])
                    else:
                        file, func = next(iter(self.functions_map[called_func].items()))
                        resolved_deps.append(func)
            else:
                inference_prompt = self.prompts.format_prompt(
                    "function_inference",
                    called_func=called_func,
                    function_name=function.name,
                    from_file=from_file if from_file else "unknown",
                )

                try:
                    inference_json = self.llm.query(inference_prompt)
                    inference = self._extract_json_from_response(inference_json)
                    inferred_func = Function(
                        inference["name"],
                        inference.get("inferred_description", "Inferred function"),
                        [],
                    )
                    inferred_func.likely_parameters = inference.get(
                        "likely_parameters", []
                    )
                    inferred_func.likely_return = inference.get(
                        "likely_return", "unknown"
                    )
                    inferred_func.is_inferred = True
                    inferred_func.qualified_name = f"inferred:{called_func}"
                    resolved_deps.append(inferred_func)
                except Exception as e:
                    print(f"Error inferring function {called_func}: {e}")
                    placeholder = {
                        "name": called_func,
                        "description": "Unknown external function",
                        "error": str(e),
                        "qualified_name": f"unknown:{called_func}",
                    }
                    resolved_deps.append(placeholder)

        function.resolved_dependencies = resolved_deps
        return [
            dep.to_dict() if hasattr(dep, "to_dict") else dep for dep in resolved_deps
        ]

    def get_dependency_graph(self) -> Dict:
        """
        Get the complete dependency graph for the repository.

        Returns:
            Dictionary mapping function names to their dependencies
        """
        graph = {}
        for func_name, file_funcs in self.functions_map.items():
            for filename, func in file_funcs.items():
                if not func.resolved_dependencies:
                    self.resolve(func_name, filename)
                graph[func.qualified_name] = [
                    dep.qualified_name
                    if hasattr(dep, "qualified_name")
                    else (
                        dep["qualified_name"]
                        if isinstance(dep, dict) and "qualified_name" in dep
                        else str(dep)
                    )
                    for dep in func.resolved_dependencies
                ]

        for method_name, method in self.methods_map.items():
            if not method.resolved_dependencies:
                self._resolve_dependencies(method)
            graph[method_name] = [
                dep.qualified_name
                if hasattr(dep, "qualified_name")
                else (
                    dep["qualified_name"]
                    if isinstance(dep, dict) and "qualified_name" in dep
                    else str(dep)
                )
                for dep in method.resolved_dependencies
            ]

        return graph

    def export_repository_structure(self) -> Dict:
        """
        Export the complete repository structure.

        Returns:
            Dictionary containing files and dependency graph
        """
        return {
            "files": {
                name: file_obj.to_dict() for name, file_obj in self.files.items()
            },
            "dependency_graph": self.get_dependency_graph(),
        }

    def generate_graph(self, graph_generator: GraphGenerator, file_path: str) -> str:
        """
        Generate a graph using the provided graph generator.

        Args:
            graph_generator: Graph generator implementation

        Returns:
            Generated graph data (URL, filepath, etc.)
        """
        code = graph_generator.generate(self.export_repository_structure())
        graph_generator.save(code, file_path)

    def _clone_github_repo(self, github_url: str) -> str:
        """
        Clone a GitHub repository to a temporary directory.

        Args:
            github_url: URL of the GitHub repository

        Returns:
            Local path of the cloned repository
        """
        temp_dir = tempfile.mkdtemp(prefix="repo_")
        cmd = ["git", "clone", github_url, temp_dir]
        subprocess.run(cmd, check=True)
        return temp_dir

    def _extract_json_from_response(self, response: str) -> Dict:
        """
        Extract JSON from an LLM response.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed JSON as a dictionary
        """
        import re
        import json

        # Try to find JSON within code blocks
        match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
        if match:
            response = match.group(1)
        else:
            # Try to find JSON anywhere in the text
            match = re.search(r"({[\s\S]*})", response, re.DOTALL)
            if match:
                response = match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(f"Raw response: {response}")
            raise
