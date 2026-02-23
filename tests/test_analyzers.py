"""Tests for code analyzers"""
import pytest
from pathlib import Path
from git_doc_hook.analyzers import get_analyzer
from git_doc_hook.analyzers.base import ComplexityMetrics


def test_get_analyzer_python():
    """Test Python analyzer selection"""
    analyzer = get_analyzer("test.py")
    assert analyzer.language == "Python"


def test_get_analyzer_javascript():
    """Test JavaScript analyzer selection"""
    analyzer = get_analyzer("test.js")
    assert analyzer.language == "JavaScript/TypeScript"


def test_get_analyzer_typescript():
    """Test TypeScript analyzer selection"""
    analyzer = get_analyzer("test.ts")
    assert analyzer.language == "JavaScript/TypeScript"


def test_get_analyzer_bash():
    """Test Bash analyzer selection"""
    analyzer = get_analyzer("test.sh")
    assert analyzer.language == "Bash"


def test_complexity_metrics():
    """Test ComplexityMetrics dataclass"""
    metrics = ComplexityMetrics(
        line_count=50,
        nesting_depth=2,
        complexity_score=3,
    )

    assert metrics.line_count == 50
    assert not metrics.is_high_complexity

    high_metrics = ComplexityMetrics(
        line_count=150,
        nesting_depth=2,
        complexity_score=3,
    )

    assert high_metrics.is_high_complexity
