"""Code analyzers for git-doc-hook

Provides language-specific analysis for complexity detection
and change categorization.
"""
from .base import BaseAnalyzer, ComplexityMetrics, AnalysisResult
from .python import PythonAnalyzer
from .javascript import JavaScriptAnalyzer
from .bash import BashAnalyzer

__all__ = [
    "BaseAnalyzer",
    "ComplexityMetrics",
    "AnalysisResult",
    "PythonAnalyzer",
    "JavaScriptAnalyzer",
    "BashAnalyzer",
]


def get_analyzer(file_path: str) -> BaseAnalyzer:
    """Get appropriate analyzer for a file

    Args:
        file_path: Path to file to analyze

    Returns:
        Appropriate analyzer instance
    """
    # Try each analyzer to see which can handle the file
    analyzers = [PythonAnalyzer(), JavaScriptAnalyzer(), BashAnalyzer()]

    for analyzer in analyzers:
        if analyzer.can_analyze(file_path):
            return analyzer

    # Return generic analyzer (base class) as fallback
    return BaseAnalyzer()
