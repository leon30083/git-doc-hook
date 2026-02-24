"""Test analyzer for demonstrating git-doc-hook functionality."""

def analyze_code(content: str) -> dict:
    """Analyze code content and return metrics."""
    return {
        "lines": len(content.split('\n')),
        "functions": content.count('def ')
    }

class CodeAnalyzer:
    """Main analyzer class."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    def process(self, file_path: str) -> dict:
        """Process a file and return analysis results."""
        with open(file_path) as f:
            content = f.read()
        return analyze_code(content)
