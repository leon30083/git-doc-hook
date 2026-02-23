"""Git-Doc-Hook setup configuration"""
from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="git-doc-hook",
    version="0.1.0",
    description="Universal Git documentation auto-update tool with MemOS integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="leon30083",
    url="https://github.com/leon30083/git-doc-hook",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "git-doc-hook=git_doc_hook.cli:main",
        ],
    },
    install_requires=[
        "pyyaml>=6.0",
        "click>=8.0",
        "jinja2>=3.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "mypy>=0.990",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
