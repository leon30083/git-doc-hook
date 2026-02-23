"""Document update module for git-doc-hook

Provides file update operations for various document types.
"""
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    """Result of a document update operation"""

    success: bool
    target_file: str
    action: str
    message: str = ""
    backup_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "target_file": self.target_file,
            "action": self.action,
            "message": self.message,
            "backup_path": self.backup_path,
        }


class DocumentUpdater:
    """Handles updates to documentation files

    Supports various update actions including table row insertion,
    content appending, and section replacement.
    """

    def __init__(self, dry_run: bool = False, backup: bool = True):
        """Initialize document updater

        Args:
            dry_run: If True, don't actually write changes
            backup: If True, create backup files before modifying
        """
        self.dry_run = dry_run
        self.backup = backup
        self._results: List[UpdateResult] = []

    def append_table_row(
        self,
        target_file: Path,
        section: str,
        row_data: Dict[str, str],
        table_headers: Optional[List[str]] = None,
    ) -> UpdateResult:
        """Append a row to a Markdown table in a section

        Args:
            target_file: Path to target file
            section: Section name to find (e.g., "Services")
            row_data: Dictionary of column names to values
            table_headers: Optional table headers (for creating new table)

        Returns:
            UpdateResult with outcome
        """
        if not target_file.exists():
            # Create file with section and table
            return self._create_table_file(target_file, section, row_data, table_headers)

        content = target_file.read_text()
        lines = content.split("\n")

        # Find section
        section_index = self._find_section_index(lines, section)
        if section_index is None:
            # Section doesn't exist, append it
            return self._append_table_section(target_file, lines, section, row_data, table_headers)

        # Find table after section
        table_start = self._find_table_after_section(lines, section_index)
        if table_start is None:
            # No table found, insert after section
            return self._insert_table_after_section(target_file, lines, section_index, row_data, table_headers)

        # Get table headers
        table_end = self._find_table_end(lines, table_start)
        headers = self._parse_table_row(lines[table_start])

        # Build row data in correct order
        row_cells = [str(row_data.get(h, "")) for h in headers]
        row_line = "| " + " | ".join(row_cells) + " |"

        # Check for separator line
        if table_start + 1 < len(lines) and lines[table_start + 1].startswith("|"):
            # Insert row after separator
            insert_index = table_start + 2
        else:
            insert_index = table_start + 1

        # Check if row already exists
        if self._row_exists(lines, table_start, table_end, row_data):
            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action="append_table_row",
                message="Row already exists in table",
            )

        # Insert the row
        lines.insert(insert_index, row_line)

        return self._write_file(target_file, lines, "append_table_row")

    def append_record(
        self,
        target_file: Path,
        content: str,
        separator: str = "\n\n---\n\n",
    ) -> UpdateResult:
        """Append content to a file

        Args:
            target_file: Path to target file
            content: Content to append
            separator: Separator between existing and new content

        Returns:
            UpdateResult with outcome
        """
        if not target_file.exists():
            # Create parent directories
            target_file.parent.mkdir(parents=True, exist_ok=True)

            if not self.dry_run:
                target_file.write_text(content + "\n")
            else:
                logger.info(f"[DRY RUN] Would create {target_file}")

            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action="append_record",
                message="Created new file with content",
            )

        existing = target_file.read_text()
        new_content = existing.rstrip() + separator + content

        if not self.dry_run:
            self._backup_file(target_file)
            target_file.write_text(new_content)
        else:
            logger.info(f"[DRY RUN] Would append to {target_file}")

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action="append_record",
            message=f"Appended {len(content)} characters",
        )

    def update_section(
        self,
        target_file: Path,
        section: str,
        new_content: str,
        replace_subsection: Optional[str] = None,
    ) -> UpdateResult:
        """Update or replace a section in a file

        Args:
            target_file: Path to target file
            section: Section name to update
            new_content: New section content
            replace_subsection: Optional subsection name to replace

        Returns:
            UpdateResult with outcome
        """
        if not target_file.exists():
            # Create file with section
            target_file.parent.mkdir(parents=True, exist_ok=True)
            content = f"## {section}\n\n{new_content}\n"

            if not self.dry_run:
                target_file.write_text(content)
            else:
                logger.info(f"[DRY RUN] Would create {target_file}")

            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action="update_section",
                message="Created new file with section",
            )

        content = target_file.read_text()
        lines = content.split("\n")

        section_index = self._find_section_index(lines, section)
        if section_index is None:
            # Append new section
            lines.append("")
            lines.append(f"## {section}")
            lines.append("")
            lines.extend(new_content.split("\n"))
        else:
            # Replace existing section content
            if replace_subsection:
                # Find and replace subsection
                subsection_index = self._find_section_index(
                    lines, replace_subsection, start=section_index + 1
                )
                if subsection_index is not None:
                    next_section = self._find_next_section_index(lines, subsection_index + 1)
                    if next_section is not None:
                        # Replace subsection content
                        lines[subsection_index + 1:next_section] = new_content.split("\n")
                    else:
                        lines[subsection_index + 1:] = new_content.split("\n")
                else:
                    # Append subsection
                    next_section = self._find_next_section_index(lines, section_index + 1)
                    if next_section is not None:
                        insert_index = next_section
                    else:
                        insert_index = len(lines)
                    lines.insert(insert_index, "")
                    lines.insert(insert_index + 1, f"### {replace_subsection}")
                    lines.insert(insert_index + 2, "")
                    for content_line in reversed(new_content.split("\n")):
                        lines.insert(insert_index + 3, content_line)
            else:
                # Replace entire section content
                next_section = self._find_next_section_index(lines, section_index + 1)
                if next_section is not None:
                    # Keep section header, replace content
                    lines[section_index + 2:next_section] = new_content.split("\n")
                else:
                    lines[section_index + 2:] = new_content.split("\n")

        return self._write_file(target_file, lines, "update_section")

    def prepend_content(
        self,
        target_file: Path,
        content: str,
        after_header: bool = True,
    ) -> UpdateResult:
        """Prepend content to a file

        Args:
            target_file: Path to target file
            content: Content to prepend
            after_header: If True, insert after first header/line

        Returns:
            UpdateResult with outcome
        """
        if not target_file.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.dry_run:
                target_file.write_text(content + "\n")
            else:
                logger.info(f"[DRY RUN] Would create {target_file}")

            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action="prepend_content",
                message="Created new file",
            )

        existing = target_file.read_text()

        if after_header:
            lines = existing.split("\n")
            # Find first non-empty line
            first_content = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith("#"):
                    first_content = i
                    break

            lines[first_content:first_content] = ["", content]
            new_content = "\n".join(lines)
        else:
            new_content = content + "\n" + existing

        if not self.dry_run:
            self._backup_file(target_file)
            target_file.write_text(new_content)
        else:
            logger.info(f"[DRY RUN] Would prepend to {target_file}")

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action="prepend_content",
            message=f"Prepended {len(content)} characters",
        )

    def _create_table_file(
        self,
        target_file: Path,
        section: str,
        row_data: Dict[str, str],
        table_headers: Optional[List[str]],
    ) -> UpdateResult:
        """Create a new file with a table"""
        headers = table_headers or list(row_data.keys())

        lines = [
            f"# Documentation",
            "",
            f"## {section}",
            "",
            self._format_table_row(headers),
            self._format_table_separator(len(headers)),
            self._format_table_row([str(row_data.get(h, "")) for h in headers]),
            "",
        ]

        target_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.dry_run:
            target_file.write_text("\n".join(lines))
        else:
            logger.info(f"[DRY RUN] Would create {target_file} with table")

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action="append_table_row",
            message="Created new file with table",
        )

    def _append_table_section(
        self,
        target_file: Path,
        lines: List[str],
        section: str,
        row_data: Dict[str, str],
        table_headers: Optional[List[str]],
    ) -> UpdateResult:
        """Append a new section with table to file"""
        headers = table_headers or list(row_data.keys())

        lines.extend([
            "",
            f"## {section}",
            "",
            self._format_table_row(headers),
            self._format_table_separator(len(headers)),
            self._format_table_row([str(row_data.get(h, "")) for h in headers]),
        ])

        return self._write_file(target_file, lines, "append_table_row")

    def _insert_table_after_section(
        self,
        target_file: Path,
        lines: List[str],
        section_index: int,
        row_data: Dict[str, str],
        table_headers: Optional[List[str]],
    ) -> UpdateResult:
        """Insert a table after a section header"""
        headers = table_headers or list(row_data.keys())

        insert_index = section_index + 2
        lines[insert_index:insert_index] = [
            "",
            self._format_table_row(headers),
            self._format_table_separator(len(headers)),
            self._format_table_row([str(row_data.get(h, "")) for h in headers]),
        ]

        return self._write_file(target_file, lines, "append_table_row")

    def _find_section_index(
        self, lines: List[str], section: str, start: int = 0
    ) -> Optional[int]:
        """Find line index of a section header"""
        section_patterns = [
            f"## {section}",
            f"### {section}",
            f"#### {section}",
        ]

        # Also try case-insensitive
        for i in range(start, len(lines)):
            line = lines[i].strip()
            for pattern in section_patterns:
                if line.lower() == pattern.lower():
                    return i

        return None

    def _find_next_section_index(self, lines: List[str], start: int = 0) -> Optional[int]:
        """Find the next section header after start index"""
        for i in range(start, len(lines)):
            if lines[i].startswith("##"):
                return i
        return None

    def _find_table_after_section(
        self, lines: List[str], section_index: int
    ) -> Optional[int]:
        """Find a table starting after a section"""
        for i in range(section_index + 1, len(lines)):
            line = lines[i].strip()
            if line.startswith("|"):
                return i
            if line.startswith("##"):
                # Next section, no table found
                return None
        return None

    def _find_table_end(self, lines: List[str], table_start: int) -> int:
        """Find the end of a table"""
        for i in range(table_start + 1, len(lines)):
            if not lines[i].strip().startswith("|"):
                return i
        return len(lines)

    def _parse_table_row(self, row: str) -> List[str]:
        """Parse a Markdown table row into cells"""
        cells = []
        for cell in row.split("|"):
            cell = cell.strip()
            if cell and not all(c in "-" for c in cell):
                cells.append(cell)
        return cells

    def _format_table_row(self, cells: List[str]) -> str:
        """Format cells as a Markdown table row"""
        return "| " + " | ".join(str(c) for c in cells) + " |"

    def _format_table_separator(self, num_cols: int) -> str:
        """Format a Markdown table separator row"""
        return "| " + " | ".join("---" for _ in range(num_cols)) + " |"

    def _row_exists(
        self,
        lines: List[str],
        table_start: int,
        table_end: int,
        row_data: Dict[str, str],
    ) -> bool:
        """Check if a row with the same data already exists"""
        # Simple check: compare first value
        first_value = str(list(row_data.values())[0]) if row_data else ""

        for i in range(table_start, min(table_end, len(lines))):
            line = lines[i]
            if first_value in line:
                return True
        return False

    def _write_file(self, target_file: Path, lines: List[str], action: str) -> UpdateResult:
        """Write lines to file with backup and dry-run support"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {target_file}")
            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action=action,
                message="Dry run - no changes made",
            )

        self._backup_file(target_file)
        target_file.write_text("\n".join(lines))

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action=action,
            message="File updated successfully",
        )

    def _backup_file(self, target_file: Path) -> Optional[str]:
        """Create a backup of the file"""
        if not self.backup or not target_file.exists():
            return None

        backup_path = target_file.with_suffix(target_file.suffix + ".bak")
        shutil.copy2(target_file, backup_path)
        logger.debug(f"Created backup: {backup_path}")
        return str(backup_path)

    def get_results(self) -> List[UpdateResult]:
        """Get all update results"""
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear stored results"""
        self._results.clear()


class ConfigFileUpdater:
    """Updater for AI assistant config files (.clinerules, .cursorrules)"""

    COMMON_PATTERNS = [
        "Testing",
        "Error Handling",
        "Code Organization",
        "File Structure",
        "Dependencies",
        "API Patterns",
    ]

    def __init__(self, dry_run: bool = False):
        """Initialize config file updater

        Args:
            dry_run: If True, don't actually write changes
        """
        self.dry_run = dry_run

    def update_clinerules(
        self,
        project_path: Path,
        patterns: List[str],
        existing_content: Optional[str] = None,
    ) -> UpdateResult:
        """Update .clinerules file with code patterns

        Args:
            project_path: Path to project
            patterns: List of code patterns detected
            existing_content: Existing file content (optional)

        Returns:
            UpdateResult with outcome
        """
        target_file = project_path / ".clinerules"
        current_content = existing_content or (target_file.read_text() if target_file.exists() else "")

        # Generate new content
        new_sections = self._generate_pattern_sections(patterns)

        # Check what's missing
        missing_patterns = []
        for pattern in patterns:
            if pattern.lower() not in current_content.lower():
                missing_patterns.append(pattern)

        if not missing_patterns:
            return UpdateResult(
                success=True,
                target_file=str(target_file),
                action="update_clinerules",
                message="All patterns already documented",
            )

        # Append missing patterns
        if current_content:
            content = current_content.rstrip() + "\n\n" + new_sections
        else:
            content = "# AI Assistant Rules\n\n" + new_sections

        if not self.dry_run:
            target_file.write_text(content)
        else:
            logger.info(f"[DRY RUN] Would update {target_file}")

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action="update_clinerules",
            message=f"Added {len(missing_patterns)} pattern sections",
        )

    def update_cursorrules(
        self,
        project_path: Path,
        patterns: List[str],
    ) -> UpdateResult:
        """Update .cursorrules file with code patterns

        Args:
            project_path: Path to project
            patterns: List of code patterns detected

        Returns:
            UpdateResult with outcome
        """
        # Similar to clinerules but with different format
        target_file = project_path / ".cursorrules"
        current_content = target_file.read_text() if target_file.exists() else ""

        # Generate cursor-specific format
        new_content = self._generate_cursor_content(patterns, current_content)

        if not self.dry_run:
            target_file.write_text(new_content)
        else:
            logger.info(f"[DRY RUN] Would update {target_file}")

        return UpdateResult(
            success=True,
            target_file=str(target_file),
            action="update_cursorrules",
            message="Updated cursor rules",
        )

    def _generate_pattern_sections(self, patterns: List[str]) -> str:
        """Generate markdown sections for patterns"""
        sections = []
        for pattern in patterns:
            sections.append(f"## {pattern}")
            sections.append("")
            sections.append(f"When working with {pattern.lower()}, follow the project conventions.")
            sections.append("")
        return "\n".join(sections)

    def _generate_cursor_content(self, patterns: List[str], existing: str) -> str:
        """Generate content for .cursorrules file"""
        rules = []

        # Add existing content
        if existing:
            rules.append(existing)

        # Add new patterns
        for pattern in patterns:
            rule = f"- Follow {pattern} conventions when working with related code"
            if rule not in existing:
                rules.append(rule)

        return "\n".join(rules) if rules else "# Project Rules\n"


def extract_code_patterns(files: List[Path], project_path: Path) -> List[str]:
    """Extract code patterns from changed files

    Args:
        files: List of changed file paths
        project_path: Project root path

    Returns:
        List of detected patterns
    """
    patterns = set()

    for file_path in files:
        # Full path resolution
        if not file_path.is_absolute():
            full_path = project_path / file_path
        else:
            full_path = file_path

        if not full_path.exists():
            continue

        # Detect patterns from path
        path_str = str(full_path)

        # Directory-based patterns
        if "test" in path_str.lower():
            patterns.add("Testing")
        if "service" in path_str.lower():
            patterns.add("Service Layer")
        if "model" in path_str.lower() or "entity" in path_str.lower():
            patterns.add("Data Models")
        if "api" in path_str.lower():
            patterns.add("API Patterns")
        if "util" in path_str.lower():
            patterns.add("Utilities")

        # Content-based patterns (for small files)
        try:
            content = full_path.read_text()
            if "def test_" in content or "describe(" in content:
                patterns.add("Testing")
            if "class " in content and "Error" in content:
                patterns.add("Error Handling")
            if "import " in content:
                patterns.add("Dependencies")
        except Exception:
            pass

    return list(patterns)
