"""JavaScript/TypeScript code analyzer

Provides analysis for JavaScript and TypeScript files using
pattern matching and AST-like parsing.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    BaseAnalyzer,
    AnalysisResult,
    ComplexityMetrics,
    FunctionInfo,
    ClassInfo,
)


class JavaScriptAnalyzer(BaseAnalyzer):
    """Analyzer for JavaScript/TypeScript code"""

    extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    @property
    def language(self) -> str:
        return "JavaScript/TypeScript"

    def can_analyze(self, file_path: str) -> bool:
        """Check if file is a JavaScript/TypeScript file"""
        return Path(file_path).suffix.lower() in self.extensions

    def analyze(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a JavaScript/TypeScript file

        Args:
            file_path: Path to the file
            context: Additional context

        Returns:
            AnalysisResult with findings
        """
        path = Path(file_path)

        try:
            source = path.read_text()
        except (IOError, UnicodeDecodeError):
            return self._empty_result(file_path)

        # Detect if TypeScript
        is_typescript = path.suffix in [".ts", ".tsx"]

        # Extract information
        functions = self._extract_functions(source)
        classes = self._extract_classes(source)
        imports = self._extract_imports_js(source)
        complexity = self._calculate_complexity_js(source)

        # Determine layers and actions
        context = context or {}
        layers = self.detect_layers(file_path, context)
        actions = self._determine_actions(file_path, context, complexity)

        return AnalysisResult(
            file_path=file_path,
            language=f"TypeScript" if is_typescript else "JavaScript",
            layers=layers,
            actions=actions,
            complexity=complexity,
            functions=functions,
            classes=classes,
            imports=imports,
            metadata={
                "file_type": self.detect_file_type(file_path),
                "is_typescript": is_typescript,
                "has_classes": len(classes) > 0,
                "has_exports": self._has_exports(source),
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
        """Extract function definitions using regex

        Args:
            source: Source code

        Returns:
            List of FunctionInfo objects
        """
        functions = []

        # Pattern for function declarations and method definitions
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'(\w+)\s*:\s*function\s*\(',
            r'(\w+)\s*\([^)]*\)\s*{',  # ES6 arrow functions and methods
            r'const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
        ]

        lines = source.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    # Skip common non-function patterns
                    if name in ["if", "for", "while", "switch", "catch"]:
                        continue

                    # Extract parameters
                    params = []
                    param_match = re.search(r'\(([^)]*)\)', line)
                    if param_match:
                        param_str = param_match.group(1)
                        if param_str.strip():
                            params = [p.strip() for p in param_str.split(",")]

                    functions.append(
                        FunctionInfo(
                            name=name,
                            line_start=i,
                            line_end=i,  # Would need full parsing for end line
                            parameters=params,
                            decorators=[],
                            is_method=False,
                            is_async="async" in line,
                        )
                    )
                    break

        return functions

    def _extract_classes(self, source: str) -> List[ClassInfo]:
        """Extract class definitions

        Args:
            source: Source code

        Returns:
            List of ClassInfo objects
        """
        classes = []
        lines = source.split("\n")

        # Pattern for class declarations
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?'

        for i, line in enumerate(lines, 1):
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                base = match.group(2)

                classes.append(
                    ClassInfo(
                        name=name,
                        line_start=i,
                        line_end=i,
                        bases=[base] if base else [],
                        methods=[],
                    )
                )

        return classes

    def _extract_imports_js(self, source: str) -> List[str]:
        """Extract import statements

        Args:
            source: Source code

        Returns:
            List of import statements
        """
        imports = []

        patterns = [
            r'import\s+.*?\s+from\s+[\'"][^\'"]+[\'"];?',
            r'import\s+[\'"][^\'"]+[\'"];?',
            r'require\([\'"][^\'"]+[\'"]\);?',
        ]

        for line in source.split("\n"):
            line = line.strip()
            for pattern in patterns:
                if re.match(pattern, line):
                    imports.append(line)
                    break

        return imports

    def _calculate_complexity_js(self, source: str) -> ComplexityMetrics:
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
            if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
                code_lines += 1

        # Calculate cyclomatic complexity
        complexity_score = 1  # Base complexity
        control_flow = ["if", "else", "for", "while", "case", "catch", "switch", "&&", "||"]

        for line in lines:
            stripped = line.strip()
            for keyword in control_flow:
                if keyword in stripped:
                    complexity_score += 1
                    break

        # Count functions and classes
        function_count = len(re.findall(r'function\s+\w+', source))
        function_count += len(re.findall(r'\w+\s*:\s*function', source))
        function_count += len(re.findall(r'\w+\s*\([^)]*\)\s*{', source))
        class_count = len(re.findall(r'class\s+\w+', source))

        # Find max parameters
        max_params = 0
        param_matches = re.findall(r'\(([^)]*)\)', source)
        for params in param_matches:
            param_count = len([p for p in params.split(",") if p.strip()])
            max_params = max(max_params, param_count)

        # Calculate max nesting depth
        max_nesting = self._calculate_nesting_depth(source)

        return ComplexityMetrics(
            line_count=line_count,
            code_lines=code_lines,
            nesting_depth=max_nesting,
            complexity_score=complexity_score,
            function_count=function_count,
            class_count=class_count,
            param_count=max_params,
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

            # Count opening brackets/keywords
            if any(kw in stripped for kw in ["if", "for", "while", "function", "=>", "class", "switch", "try", "catch"]):
                if "{" in stripped or ":" in stripped:
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)

            # Count closing brackets
            current_depth -= stripped.count("}")
            current_depth = max(0, current_depth)

        return max_depth

    def _has_exports(self, source: str) -> bool:
        """Check if file has exports

        Args:
            source: Source code

        Returns:
            True if file exports something
        """
        return bool(
            re.search(r'export\s+(default\s+)?', source)
            or re.search(r'module\.exports', source)
        )

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

        # Check for component additions
        if "component" in path.parts or "components" in path.parts:
            if any(kw in commit_message for kw in ["feat", "add", "new"]):
                actions.append({
                    "target": "README.md",
                    "section": "Components",
                    "action": "append_table_row",
                    "data": {
                        "name": path.stem,
                        "file": str(path),
                    },
                })

        # High complexity changes
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
