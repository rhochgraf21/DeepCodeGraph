"""
-------------------------------
Domain Model Classes
-------------------------------

This module provides classes to represent key portions of code used in the 
abstract AST.
"""
from typing import Dict, List


class CodeElement:
    """Base class for code elements."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def to_dict(self) -> Dict:
        return {"name": self.name, "description": self.description}


class Function(CodeElement):
    """Represents a function in the codebase, including type hints if available."""

    def __init__(
        self,
        name: str,
        description: str,
        called_functions: List[str] = None,
        parameters: List[Dict[str, str]] = None,
        return_type: str = None,
    ):
        super().__init__(name, description)
        self.called_functions = called_functions or []
        self.parameters = (
            parameters or []
        )  # Each parameter is a dict with "name" and "type"
        self.return_type = return_type
        self.resolved_dependencies = (
            []
        )  # List of resolved dependencies (Function/Method objects)
        self.qualified_name = None

    def to_dict(self) -> Dict:
        result = super().to_dict()
        result.update(
            {
                "called_functions": self.called_functions,
                "parameters": self.parameters,
                "return_type": self.return_type,
                "resolved_dependencies": [
                    dep.qualified_name if hasattr(dep, "qualified_name") else str(dep)
                    for dep in self.resolved_dependencies
                ],
                "qualified_name": self.qualified_name,
            }
        )
        return result


class Method(Function):
    """Represents a method belonging to a class."""

    def __init__(
        self,
        name: str,
        description: str,
        class_name: str,
        called_functions: List[str] = None,
        parameters: List[Dict[str, str]] = None,
        return_type: str = None,
    ):
        super().__init__(name, description, called_functions, parameters, return_type)
        self.class_name = class_name

    def to_dict(self) -> Dict:
        result = super().to_dict()
        result["class_name"] = self.class_name
        return result


class Class(CodeElement):
    """Represents a class in the codebase."""

    def __init__(self, name: str, description: str, methods: List[Method] = None):
        super().__init__(name, description)
        self.methods = methods or []

    def add_method(self, method: Method):
        self.methods.append(method)

    def to_dict(self) -> Dict:
        result = super().to_dict()
        result["methods"] = [method.to_dict() for method in self.methods]
        return result


class Global(CodeElement):
    """Represents a global variable in the codebase."""

    def __init__(self, name: str, description: str, value: str = None):
        super().__init__(name, description)
        self.value = value

    def to_dict(self) -> Dict:
        result = super().to_dict()
        if self.value:
            result["value"] = self.value
        return result


class File:
    """Represents a file in the codebase."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.functions: List[Function] = []
        self.classes: List[Class] = []
        self.globals: List[Global] = []
        self.raw_code: str = ""
        self.imports: List[str] = []  # List of imported file/module names

    def add_function(self, function: Function):
        function.qualified_name = f"{self.name}:{function.name}"
        self.functions.append(function)

    def add_class(self, cls: Class):
        self.classes.append(cls)

    def add_global(self, glob: Global):
        self.globals.append(glob)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "functions": [func.to_dict() for func in self.functions],
            "classes": [cls.to_dict() for cls in self.classes],
            "globals": [glob.to_dict() for glob in self.globals],
            "imports": self.imports,
        }
