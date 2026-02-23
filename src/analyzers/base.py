"""Base analyzer class and common types

Defines the abstract interface that all analyzers must implement
along with common data structures.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ComplexityMetrics:
    """Generic complexity metrics for code analysis

    Attributes:
        line_count: Total lines of code
        code_lines: Lines of actual code (excluding blanks/comments)
        nesting_depth: Maximum nesting depth
        complexity_score: Cyclomatic complexity estimate
        function_count: Number of functions/methods
        class_count: Number of classes
        param_count: Maximum parameter count
    """

    line_count: int
    code_lines: int = 0
    nesting_depth: int = 0
    complexity_score: int = 0
    function_count: int = 0
    class_count: int = 0
    param_count: int = 0

    @property
    def is_high_complexity(self) -> bool:
        """Check if this indicates high complexity"""
        return (
            self.line_count > 100
            or self.nesting_depth > 4
            or self.complexity_score > 10
        )

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary"""
        return {
            "line_count": self.line_count,
            "code_lines": self.code_lines,
            "nesting_depth": self.nesting_depth,
            "complexity_score": self.complexity_score,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "param_count": self.param_count,
        }


@dataclass
class FunctionInfo:
    """Information about a function or method

    Attributes:
        name: Function name
        line_start: Starting line number
        line_end: Ending line number
        parameters: List of parameter names
        decorators: List of decorator names
        is_method: True if this is a class method
        is_async: True if async function
    """

    name: str
    line_start: int
    line_end: int
    parameters: List[str]
    decorators: List[str]
    is_method: bool = False
    is_async: bool = False

    @property
    def line_count(self) -> int:
        """Number of lines in this function"""
        return self.line_end - self.line_start + 1


@dataclass
class ClassInfo:
    """Information about a class

    Attributes:
        name: Class name
        line_start: Starting line number
        line_end: Ending line number
        bases: List of base class names
        methods: List of methods in this class
    """

    name: str
    line_start: int
    line_end: int
    bases: List[str]
    methods: List[FunctionInfo]


@dataclass
class AnalysisResult:
    """Result of code analysis

    Attributes:
        file_path: Path to the analyzed file
        language: Programming language
        layers: Document layers that should be updated
        actions: List of actions to take
        complexity: Optional complexity metrics
        functions: List of functions found
        classes: List of classes found
        imports: List of import statements
        metadata: Additional metadata
    """

    file_path: str
    language: str
    layers: List[str]
    actions: List[Dict[str, Any]]
    complexity: Optional[ComplexityMetrics] = None
    functions: List[FunctionInfo] = None
    classes: List[ClassInfo] = None
    imports: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.functions is None:
            self.functions = []
        if self.classes is None:
            self.classes = []
        if self.imports is None:
            self.imports = []
        if self.metadata is None:
            self.metadata = {}

    def has_high_complexity(self) -> bool:
        """Check if the analyzed code has high complexity"""
        return self.complexity is not None and self.complexity.is_high_complexity

    def get_functions_changed(
        self, changed_lines: Optional[List[int]] = None
    ) -> List[FunctionInfo]:
        """Get functions that were changed

        Args:
            changed_lines: List of line numbers that were changed

        Returns:
            List of changed functions
        """
        if not changed_lines:
            return []

        changed = []
        for func in self.functions:
            # Check if any changed line is within this function
            if any(func.line_start <= line <= func.line_end for line in changed_lines):
                changed.append(func)
        return changed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "layers": self.layers,
            "actions": self.actions,
            "complexity": self.complexity.to_dict() if self.complexity else None,
            "function_count": len(self.functions),
            "class_count": len(self.classes),
            "imports": self.imports,
            "metadata": self.metadata,
        }


class BaseAnalyzer(ABC):
    """Base class for code analyzers

    All language-specific analyzers should inherit from this class
    and implement the required methods.
    """

    # File extensions this analyzer handles
    extensions: List[str] = []

    @property
    @abstractmethod
    def language(self) -> str:
        """Return the language name this analyzer handles"""
        pass

    @abstractmethod
    def can_analyze(self, file_path: str) -> bool:
        """Check if this analyzer can handle the given file

        Args:
            file_path: Path to the file

        Returns:
            True if this analyzer can analyze the file
        """
        pass

    @abstractmethod
    def analyze(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a file and return results

        Args:
            file_path: Path to the file to analyze
            context: Additional context (commit message, changed lines, etc.)

        Returns:
            AnalysisResult with findings
        """
        pass

    def calculate_complexity(self, source: str) -> ComplexityMetrics:
        """Calculate basic complexity metrics from source code

        Args:
            source: Source code string

        Returns:
            ComplexityMetrics object
        """
        lines = source.split("\n")

        line_count = len(lines)
        code_lines = 0
        nesting_depth = 0
        max_nesting = 0

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                code_lines += 1

            # Track nesting
            if "{" in line or ":" in line and not stripped.startswith("#"):
                nesting_depth += 1
                max_nesting = max(max_nesting, nesting_depth)
            if "}" in line:
                nesting_depth = max(0, nesting_depth - 1)

        return ComplexityMetrics(
            line_count=line_count,
            code_lines=code_lines,
            nesting_depth=max_nesting,
            complexity_score=self._calculate_cyclomatic(source),
        )

    def _calculate_cyclomatic(self, source: str) -> int:
        """Calculate cyclomatic complexity estimate

        Args:
            source: Source code string

        Returns:
            Estimated cyclomatic complexity
        """
        # Count branching keywords
        keywords = [
            "if", "else", "elif", "for", "while", "case", "switch",
            "catch", "try", "except", "finally", "and", "or"
        ]

        complexity = 1  # Base complexity
        for line in source.split("\n"):
            stripped = line.strip()
            for keyword in keywords:
                if stripped.startswith(keyword + " ") or keyword + " " in stripped:
                    complexity += 1
                    break

        return complexity

    def extract_imports(self, source: str) -> List[str]:
        """Extract import statements from source

        Args:
            source: Source code string

        Returns:
            List of import statements
        """
        imports = []
        for line in source.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)
        return imports

    def detect_layers(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Detect which document layers should be updated

        Args:
            file_path: Path to the file
            context: Analysis context

        Returns:
            List of layer names
        """
        context = context or {}
        layers = []

        # Check commit message for keywords
        commit_message = context.get("commit_message", "").lower()

        if any(kw in commit_message for kw in ["fix", "bug", "error"]):
            layers.append("memo")  # Troubleshooting record

        if any(kw in commit_message for kw in ["decision", "选型", "architecture"]):
            layers.append("memo")  # ADR record

        # Default: always consider traditional docs
        layers.append("traditional")

        return list(set(layers))

    def detect_file_type(self, file_path: str) -> str:
        """Detect the type/category of a file

        Args:
            file_path: Path to the file

        Returns:
            File type (e.g., "service", "model", "utility")
        """
        path = Path(file_path)

        # Check directory names
        if "service" in path.parent.name.lower():
            return "service"
        if "model" in path.parent.name.lower():
            return "model"
        if "util" in path.parent.name.lower():
            return "utility"
        if "test" in path.parent.name.lower():
            return "test"

        # Check file name
        if path.name.startswith("test_"):
            return "test"

        return "unknown"
