"""Python code analyzer using AST parsing

Provides detailed analysis of Python code including complexity,
function detection, and dependency extraction.
"""
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    BaseAnalyzer,
    AnalysisResult,
    ComplexityMetrics,
    FunctionInfo,
    ClassInfo,
)


class PythonAnalyzer(BaseAnalyzer):
    """Analyzer for Python code using AST parsing"""

    extensions = [".py"]

    @property
    def language(self) -> str:
        return "Python"

    def can_analyze(self, file_path: str) -> bool:
        """Check if file is a Python file"""
        return Path(file_path).suffix.lower() in self.extensions

    def analyze(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a Python file

        Args:
            file_path: Path to the Python file
            context: Additional context (commit message, changed lines, etc.)

        Returns:
            AnalysisResult with findings
        """
        path = Path(file_path)

        try:
            source = path.read_text()
        except (IOError, UnicodeDecodeError):
            return self._empty_result(file_path)

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # File has syntax errors, return basic analysis
            complexity = self.calculate_complexity(source)
            return AnalysisResult(
                file_path=file_path,
                language=self.language,
                layers=["traditional"],
                actions=[],
                complexity=complexity,
            )

        # Extract information
        functions = self._extract_functions(tree)
        classes = self._extract_classes(tree, source)
        imports = self._extract_imports_ast(tree)
        complexity = self._calculate_complexity_ast(tree, source)

        # Determine layers and actions
        context = context or {}
        layers = self.detect_layers(file_path, context)
        actions = self._determine_actions(file_path, context, complexity)

        return AnalysisResult(
            file_path=file_path,
            language=self.language,
            layers=layers,
            actions=actions,
            complexity=complexity,
            functions=functions,
            classes=classes,
            imports=imports,
            metadata={
                "file_type": self.detect_file_type(file_path),
                "has_classes": len(classes) > 0,
                "has_tests": any("test" in f.name.lower() for f in functions),
            },
        )

    def _empty_result(self, file_path: str) -> AnalysisResult:
        """Return an empty analysis result"""
        return AnalysisResult(
            file_path=file_path,
            language=self.language,
            layers=[],
            actions=[],
        )

    def _extract_functions(self, tree: ast.AST) -> List[FunctionInfo]:
        """Extract all function definitions

        Args:
            tree: AST tree

        Returns:
            List of FunctionInfo objects
        """
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                decorators = [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                parameters = [arg.arg for arg in node.args.args]

                functions.append(
                    FunctionInfo(
                        name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        parameters=parameters,
                        decorators=decorators,
                        is_method=False,  # Will be updated by class extraction
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )
                )

        return functions

    def _extract_classes(self, tree: ast.AST, source: str) -> List[ClassInfo]:
        """Extract all class definitions

        Args:
            tree: AST tree
            source: Source code

        Returns:
            List of ClassInfo objects
        """
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get base classes
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.get_source_segment(source, base) or "")

                # Get methods
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        decorators = [
                            d.id if isinstance(d, ast.Name) else str(d)
                            for d in item.decorator_list
                        ]
                        parameters = [arg.arg for arg in item.args.args]

                        methods.append(
                            FunctionInfo(
                                name=item.name,
                                line_start=item.lineno,
                                line_end=item.end_lineno or item.lineno,
                                parameters=parameters,
                                decorators=decorators,
                                is_method=True,
                                is_async=isinstance(item, ast.AsyncFunctionDef),
                            )
                        )

                classes.append(
                    ClassInfo(
                        name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        bases=bases,
                        methods=methods,
                    )
                )

        return classes

    def _extract_imports_ast(self, tree: ast.AST) -> List[str]:
        """Extract import statements using AST

        Args:
            tree: AST tree

        Returns:
            List of import statements
        """
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(f"from {module} import {', '.join(names)}")

        return imports

    def _calculate_complexity_ast(
        self, tree: ast.AST, source: str
    ) -> ComplexityMetrics:
        """Calculate complexity using AST

        Args:
            tree: AST tree
            source: Source code

        Returns:
            ComplexityMetrics object
        """
        lines = source.split("\n")
        line_count = len(lines)

        # Count code lines (non-blank, non-comment)
        code_lines = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                code_lines += 1

        # Calculate cyclomatic complexity
        complexity_score = 1  # Base complexity

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity_score += 1
            elif isinstance(node, (ast.BoolOp, ast.Compare)):
                complexity_score += 1

        # Count functions and classes
        function_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

        # Find max parameters
        max_params = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                param_count = len(node.args.args)
                max_params = max(max_params, param_count)

        # Calculate max nesting depth
        max_nesting = self._calculate_nesting_depth(tree)

        return ComplexityMetrics(
            line_count=line_count,
            code_lines=code_lines,
            nesting_depth=max_nesting,
            complexity_score=complexity_score,
            function_count=function_count,
            class_count=class_count,
            param_count=max_params,
        )

    def _calculate_nesting_depth(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth

        Args:
            tree: AST tree

        Returns:
            Maximum nesting depth
        """
        max_depth = 0

        def count_nesting(node, depth=0):
            nonlocal max_depth
            max_depth = max(max_depth, depth)

            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                    count_nesting(child, depth + 1)
                else:
                    count_nesting(child, depth)

        count_nesting(tree)
        return max_depth

    def _determine_actions(
        self,
        file_path: str,
        context: Dict[str, Any],
        complexity: ComplexityMetrics,
    ) -> List[Dict[str, Any]]:
        """Determine what actions should be taken

        Args:
            file_path: Path to the file
            context: Analysis context
            complexity: Complexity metrics

        Returns:
            List of action definitions
        """
        actions = []
        commit_message = context.get("commit_message", "").lower()
        path = Path(file_path)

        # Check if this is a service file
        if "service" in path.parts or "services" in path.parts:
            if any(kw in commit_message for kw in ["feat", "add", "new"]):
                actions.append({
                    "target": "README.md",
                    "section": "Services",
                    "action": "append_table_row",
                    "data": {
                        "name": path.stem,
                        "file": str(path),
                    },
                })

        # High complexity changes should trigger documentation
        if complexity.is_high_complexity:
            actions.append({
                "target": "docs/architecture.md",
                "action": "append_complexity_note",
                "data": {
                    "file": file_path,
                    "complexity": complexity.to_dict(),
                },
            })

        return actions

    def get_function_at_line(self, file_path: str, line_no: int) -> Optional[FunctionInfo]:
        """Get function at a specific line

        Args:
            file_path: Path to the file
            line_no: Line number

        Returns:
            FunctionInfo or None
        """
        try:
            source = Path(file_path).read_text()
            tree = ast.parse(source, filename=file_path)
        except (IOError, SyntaxError):
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.lineno <= line_no <= (node.end_lineno or node.lineno):
                    parameters = [arg.arg for arg in node.args.args]
                    return FunctionInfo(
                        name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        parameters=parameters,
                        decorators=[],
                        is_method=False,
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )

        return None
