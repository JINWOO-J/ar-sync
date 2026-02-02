"""Unit tests for template data models.

Tests the TemplateMetadata and CopyResult dataclasses including
their properties and edge cases.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from pathlib import Path

from ar_sync.template_models import CopyResult, TemplateMetadata


class TestTemplateMetadata:
    """Test suite for TemplateMetadata dataclass."""

    def test_basic_creation(self):
        """Test basic TemplateMetadata creation with all fields."""
        metadata = TemplateMetadata(
            name="architect",
            description="Software architecture specialist",
            category="agents",
            path=Path("/templates/agents/architect.md"),
            is_directory=False,
        )

        assert metadata.name == "architect"
        assert metadata.description == "Software architecture specialist"
        assert metadata.category == "agents"
        assert metadata.path == Path("/templates/agents/architect.md")
        assert metadata.is_directory is False

    def test_display_name_with_hyphens(self):
        """Test display_name converts hyphens to spaces and title case."""
        metadata = TemplateMetadata(
            name="code-review-expert",
            description="",
            category="agents",
            path=Path("/templates/agents/code-review-expert.md"),
            is_directory=False,
        )

        assert metadata.display_name == "Code Review Expert"

    def test_display_name_without_hyphens(self):
        """Test display_name with single word name."""
        metadata = TemplateMetadata(
            name="architect",
            description="",
            category="agents",
            path=Path("/templates/agents/architect.md"),
            is_directory=False,
        )

        assert metadata.display_name == "Architect"

    def test_short_description_under_limit(self):
        """Test short_description returns full text when under 50 chars."""
        description = "A short description"
        metadata = TemplateMetadata(
            name="test",
            description=description,
            category="rules",
            path=Path("/templates/rules/test.md"),
            is_directory=False,
        )

        assert metadata.short_description == description
        assert len(metadata.short_description) == len(description)

    def test_short_description_at_limit(self):
        """Test short_description returns full text when exactly 50 chars."""
        description = "A" * 50  # Exactly 50 characters
        metadata = TemplateMetadata(
            name="test",
            description=description,
            category="rules",
            path=Path("/templates/rules/test.md"),
            is_directory=False,
        )

        assert metadata.short_description == description
        assert len(metadata.short_description) == 50

    def test_short_description_over_limit(self):
        """Test short_description truncates with ellipsis when over 50 chars."""
        description = "A" * 60  # 60 characters
        metadata = TemplateMetadata(
            name="test",
            description=description,
            category="rules",
            path=Path("/templates/rules/test.md"),
            is_directory=False,
        )

        assert metadata.short_description == "A" * 47 + "..."
        assert len(metadata.short_description) == 50

    def test_skills_category_is_directory(self):
        """Test skills category templates are directories."""
        metadata = TemplateMetadata(
            name="web-search",
            description="Web search skill",
            category="skills",
            path=Path("/templates/skills/web-search"),
            is_directory=True,
        )

        assert metadata.category == "skills"
        assert metadata.is_directory is True

    def test_empty_description(self):
        """Test template with empty description (Requirement 1.3)."""
        metadata = TemplateMetadata(
            name="simple-template",
            description="",
            category="rules",
            path=Path("/templates/rules/simple.md"),
            is_directory=False,
        )

        assert metadata.description == ""
        assert metadata.short_description == ""


class TestCopyResult:
    """Test suite for CopyResult dataclass."""

    def test_empty_result(self):
        """Test CopyResult with default empty lists."""
        result = CopyResult()

        assert result.success == []
        assert result.skipped == []
        assert result.failed == []
        assert result.total_count == 0
        assert result.success_count == 0
        assert result.has_failures is False

    def test_success_only(self):
        """Test CopyResult with only successful copies."""
        result = CopyResult(
            success=[Path("/dest/file1.md"), Path("/dest/file2.md")],
        )

        assert result.total_count == 2
        assert result.success_count == 2
        assert result.has_failures is False

    def test_with_skipped(self):
        """Test CopyResult with skipped files."""
        result = CopyResult(
            success=[Path("/dest/file1.md")],
            skipped=[Path("/dest/file2.md")],
        )

        assert result.total_count == 2
        assert result.success_count == 1
        assert result.has_failures is False

    def test_with_failures(self):
        """Test CopyResult with failed copies."""
        result = CopyResult(
            success=[Path("/dest/file1.md")],
            failed=[(Path("/dest/file2.md"), "Permission denied")],
        )

        assert result.total_count == 2
        assert result.success_count == 1
        assert result.has_failures is True

    def test_mixed_results(self):
        """Test CopyResult with success, skipped, and failed."""
        result = CopyResult(
            success=[Path("/dest/file1.md"), Path("/dest/file2.md")],
            skipped=[Path("/dest/file3.md")],
            failed=[
                (Path("/dest/file4.md"), "Permission denied"),
                (Path("/dest/file5.md"), "Disk full"),
            ],
        )

        assert result.total_count == 5
        assert result.success_count == 2
        assert result.has_failures is True
        assert len(result.failed) == 2

    def test_failed_with_error_messages(self):
        """Test CopyResult failed entries contain error messages."""
        result = CopyResult(
            failed=[
                (Path("/dest/file1.md"), "Permission denied"),
                (Path("/dest/file2.md"), "File not found"),
            ],
        )

        assert result.failed[0] == (Path("/dest/file1.md"), "Permission denied")
        assert result.failed[1] == (Path("/dest/file2.md"), "File not found")
