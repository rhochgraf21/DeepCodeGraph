"""
-------------------------------
Domain Model Classes
-------------------------------

This module provides classes to represent key portions of code used in the 
abstract AST.
"""
from typing import Dict, List, Optional, Any # Ensure Any is present


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Function':
        func = cls(
            data['name'],
            data.get('description', ''),
            data.get('called_functions', []),
            data.get('parameters', []),
            data.get('return_type')
        )
        func.qualified_name = data.get('qualified_name')
        # resolved_dependencies are usually populated later, not from basic dict
        func.resolved_dependencies = [] 
        return func


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Method':
        method = cls(
            data['name'],
            data.get('description', ''),
            data['class_name'], 
            data.get('called_functions', []),
            data.get('parameters', []),
            data.get('return_type')
        )
        method.qualified_name = data.get('qualified_name')
        method.resolved_dependencies = []
        return method


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Class':
        class_obj = cls(data['name'], data.get('description', ''))
        class_obj.methods = [Method.from_dict(m_data) for m_data in data.get('methods', [])]
        return class_obj


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Global':
        return cls(data['name'], data.get('description', ''), data.get('value'))


class File:
    """Represents a file in the codebase."""

    def __init__(self, name: str, description: str, content_hash: Optional[str] = None,
                 raw_code: str = "", imports: Optional[List[str]] = None): # Ensure all existing args are kept
        self.name = name
        self.description = description
        self.content_hash = content_hash # Initialize it
        self.functions: List[Function] = []
        self.classes: List[Class] = []
        self.globals: List[Global] = []
        self.raw_code: str = raw_code
        self.imports: List[str] = imports or []  # List of imported file/module names

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
            "content_hash": self.content_hash, # Add content_hash here
            "functions": [func.to_dict() for func in self.functions],
            "classes": [cls.to_dict() for cls in self.classes],
            "globals": [glob.to_dict() for glob in self.globals],
            "imports": self.imports,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'File':
        # Ensure all necessary fields for File's __init__ are pulled from data or defaulted
        file_obj = cls(
            data['name'], 
            data.get('description', ''), 
            data.get('content_hash'),
            raw_code=data.get('raw_code', ''), # Provide default for raw_code
            imports=data.get('imports', [])      # Provide default for imports
        )
        # Order of operations: functions, classes, globals must be added *after* file_obj is created.
        # The File.__init__ should not call add_function etc.
        # from_dict should populate these lists directly after creating the File instance.
        
        # Correct approach for File.from_dict regarding lists of objects:
        # Create the basic File object first
        # file_obj = cls(name=data['name'], description=data.get('description', ''), content_hash=data.get('content_hash'))
        # file_obj.raw_code = data.get('raw_code', '') # If raw_code is part of export/import
        # file_obj.imports = data.get('imports', [])
        
        # Then populate its lists:
        file_obj.functions = []
        for func_data in data.get('functions', []):
            func = Function.from_dict(func_data)
            func.qualified_name = f"{file_obj.name}:{func.name}" # Set qualified_name here
            file_obj.functions.append(func)
        
        file_obj.classes = [Class.from_dict(c_data) for c_data in data.get('classes', [])]
        file_obj.globals = [Global.from_dict(g_data) for g_data in data.get('globals', [])]
        return file_obj
