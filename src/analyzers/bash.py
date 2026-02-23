"""Bash script analyzer

Provides analysis for shell scripts and bash files.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    BaseAnalyzer,
    AnalysisResult,
    ComplexityMetrics,
    FunctionInfo,
)


class BashAnalyzer(BaseAnalyzer):
    """Analyzer for Bash/Shell scripts"""

    extensions = [".sh", ".bash", ".zsh"]

    @property
    def language(self) -> str:
        return "Bash"

    def can_analyze(self, file_path: str) -> bool:
        """Check if file is a Bash script"""
        path = Path(file_path)

        # Check extension
        if path.suffix.lower() in self.extensions:
            return True

        # Check shebang
        try:
            first_line = path.open().readline()
            if first_line.startswith("#!") and any(
                shell in first_line for shell in ["bash", "sh", "zsh"]
            ):
                return True
        except (IOError, UnicodeDecodeError):
            pass

        return False

    def analyze(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a Bash script

        Args:
            file_path: Path to the script
            context: Additional context

        Returns:
            AnalysisResult with findings
        """
        path = Path(file_path)

        try:
            source = path.read_text()
        except (IOError, UnicodeDecodeError):
            return self._empty_result(file_path)

        # Extract information
        functions = self._extract_functions(source)
        imports = self._extract_sources(source)
        complexity = self._calculate_complexity_bash(source)

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
            imports=imports,
            metadata={
                "file_type": self.detect_file_type(file_path),
                "has_shebang": source.startswith("#!"),
                "is_executable": self._is_executable(path),
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

    def _extract_functions(self, source: str) -> List[FunctionInfo]:
        """Extract function definitions

        Args:
            source: Source code

        Returns:
            List of FunctionInfo objects
        """
        functions = []
        lines = source.split("\n")

        # Pattern for function definitions
        # Supports: function_name() {, function function_name {, function function_name()
        patterns = [
            r'^(\w+)\s*\(\s*\)\s*{',  # standard function_name() {
            r'^function\s+(\w+)\s*',   # function keyword
            r'^(\w+)\s*\(\s*\)',        # function_name()
        ]

        for i, line in enumerate(lines, 1):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    functions.append(
                        FunctionInfo(
                            name=match.group(1),
                            line_start=i,
                            line_end=i,
                            parameters=[],
                            decorators=[],
                            is_method=False,
                            is_async=False,
                        )
                    )
                    break

        return functions

    def _extract_sources(self, source: str) -> List[str]:
        """Extract source/include statements

        Args:
            source: Source code

        Returns:
            List of source statements
        """
        sources = []

        for line in source.split("\n"):
            line = line.strip()
            if line.startswith("source ") or line.startswith(". "):
                sources.append(line)

        return sources

    def _calculate_complexity_bash(self, source: str) -> ComplexityMetrics:
        """Calculate complexity metrics

        Args:
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
        control_flow = ["if", "then", "elif", "else", "for", "while", "case", "esac", "||", "&&"]

        for line in lines:
            stripped = line.strip()
            for keyword in control_flow:
                if keyword in stripped and not stripped.startswith("#"):
                    complexity_score += 1
                    break

        # Count functions
        function_count = len(
            [l for l in lines if re.match(r'^\s*(function\s+)?\w+\s*\(\s*\)', l)]
        )

        # Calculate max nesting depth
        max_nesting = self._calculate_nesting_depth(source)

        return ComplexityMetrics(
            line_count=line_count,
            code_lines=code_lines,
            nesting_depth=max_nesting,
            complexity_score=complexity_score,
            function_count=function_count,
            param_count=0,  # Bash functions don't have explicit parameters
        )

    def _calculate_nesting_depth(self, source: str) -> int:
        """Calculate maximum nesting depth

        Args:
            source: Source code

        Returns:
            Maximum nesting depth
        """
        max_depth = 0
        current_depth = 0

        for line in source.split("\n"):
            stripped = line.strip()

            # Keywords that increase nesting
            if any(
                kw in stripped for kw in ["if", "then", "for", "while", "case"]
            ) and not stripped.startswith("#"):
                current_depth += 1
                max_depth = max(max_depth, current_depth)

            # Keywords that decrease nesting
            if any(kw in stripped for kw in ["fi", "done", "esac"]):
                current_depth = max(0, current_depth - 1)

        return max_depth

    def _is_executable(self, path: Path) -> bool:
        """Check if file is executable

        Args:
            path: Path to file

        Returns:
            True if executable
        """
        try:
            return path.stat().st_mode & 0o111 != 0
        except OSError:
            return False

    def _determine_actions(
        self,
        file_path: str,
        context: Dict[str, Any],
        complexity: ComplexityMetrics,
    ) -> List[Dict[str, Any]]:
        """Determine what actions should be taken

        Args:
            file_path: Path to the script
            context: Analysis context
            complexity: Complexity metrics

        Returns:
            List of action definitions
        """
        actions = []
        path = Path(file_path)

        # Check if this is a tool/script
        if "tool" in path.parts or "tools" in path.parts or "bin" in path.parts:
            actions.append({
                "target": "README.md",
                "section": "Tools",
                "action": "append_table_row",
                "data": {
                    "name": path.stem,
                    "file": str(path),
                },
            })

        # High complexity scripts should be documented
        if complexity.is_high_complexity:
            actions.append({
                "target": "docs/tools.md",
                "action": "append_complexity_note",
                "data": {
                    "file": file_path,
                    "complexity": complexity.to_dict(),
                },
            })

        return actions
