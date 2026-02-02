"""Unit tests for TemplateManager.

Tests the TemplateManager class including frontmatter parsing,
template scanning, and search functionality.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.3
"""


import pytest

from ar_sync.errors import ARSyncError
from ar_sync.template_manager import TemplateManager


class TestParseFrontmatter:
    """Test suite for parse_frontmatter static method."""

    def test_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter."""
        content = """---
name: architect
description: Software architecture specialist
tools: ["Read", "Grep"]
---
Body content here.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata["name"] == "architect"
        assert metadata["description"] == "Software architecture specialist"
        assert metadata["tools"] == ["Read", "Grep"]
        assert body.strip() == "Body content here."

    def test_frontmatter_with_multiline_description(self):
        """Test parsing frontmatter with multiline description."""
        content = """---
name: test
description: >
  This is a long description
  that spans multiple lines.
---
Body content.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata["name"] == "test"
        assert "long description" in metadata["description"]
        assert body.strip() == "Body content."

    def test_no_frontmatter(self):
        """Test content without frontmatter returns empty dict."""
        content = """# Just a markdown file
No frontmatter here.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata == {}
        assert body == content

    def test_empty_frontmatter(self):
        """Test empty frontmatter block."""
        content = """---
---
Body content.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata == {}
        assert body.strip() == "Body content."

    def test_invalid_yaml_frontmatter(self):
        """Test invalid YAML returns empty dict."""
        content = """---
name: [invalid yaml
description: missing bracket
---
Body content.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata == {}
        # Body should still be extracted after the closing ---
        assert "Body content." in body

    def test_frontmatter_only_at_start(self):
        """Test that --- in middle of file is not treated as frontmatter."""
        content = """Some content first.
---
name: not-frontmatter
---
More content.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata == {}
        assert body == content

    def test_frontmatter_with_special_characters(self):
        """Test frontmatter with special characters in values."""
        content = """---
name: test-template
description: "Contains: colons, 'quotes', and special chars!"
---
Body.
"""
        metadata, body = TemplateManager.parse_frontmatter(content)

        assert metadata["name"] == "test-template"
        assert "colons" in metadata["description"]


class TestTemplateManagerInit:
    """Test suite for TemplateManager initialization."""

    def test_init_with_valid_directory(self, tmp_path):
        """Test initialization with valid templates directory."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        assert manager.templates_dir == templates_dir

    def test_init_with_nonexistent_directory(self, tmp_path):
        """Test initialization raises error for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ARSyncError) as exc_info:
            TemplateManager(nonexistent)

        assert "Templates directory not found" in str(exc_info.value)
        assert exc_info.value.recovery_steps

    def test_init_with_default_directory(self):
        """Test initialization with default templates directory."""
        # This should work if templates/ exists in project root
        manager = TemplateManager()

        assert manager.templates_dir.exists()
        assert manager.templates_dir.name == "templates"


class TestScanTemplates:
    """Test suite for scan_templates method."""

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty templates directory."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert result == {"agents": [], "rules": [], "skills": []}

    def test_scan_agents_category(self, tmp_path):
        """Test scanning agents category with frontmatter."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        # Create template with frontmatter
        (agents_dir / "architect.md").write_text("""---
name: architect
description: Software architecture specialist
---
Content here.
""")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["agents"]) == 1
        assert result["agents"][0].name == "architect"
        assert result["agents"][0].description == "Software architecture specialist"
        assert result["agents"][0].category == "agents"
        assert result["agents"][0].is_directory is False

    def test_scan_template_without_frontmatter(self, tmp_path):
        """Test scanning template without frontmatter uses filename."""
        templates_dir = tmp_path / "templates"
        rules_dir = templates_dir / "rules"
        rules_dir.mkdir(parents=True)

        # Create template without frontmatter
        (rules_dir / "coding-style.md").write_text("# Coding Style\nJust content.")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["rules"]) == 1
        assert result["rules"][0].name == "coding-style"  # stem of filename
        assert result["rules"][0].description == ""

    def test_scan_skills_directory(self, tmp_path):
        """Test scanning skills category (directories)."""
        templates_dir = tmp_path / "templates"
        skills_dir = templates_dir / "skills"
        skill_template = skills_dir / "web-search"
        skill_template.mkdir(parents=True)

        # Create SKILL.md with frontmatter
        (skill_template / "SKILL.md").write_text("""---
name: web-search
description: Web search capability
---
Skill content.
""")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["skills"]) == 1
        assert result["skills"][0].name == "web-search"
        assert result["skills"][0].description == "Web search capability"
        assert result["skills"][0].is_directory is True

    def test_scan_skills_without_skill_md(self, tmp_path):
        """Test scanning skills directory without SKILL.md uses dirname."""
        templates_dir = tmp_path / "templates"
        skills_dir = templates_dir / "skills"
        skill_template = skills_dir / "custom-skill"
        skill_template.mkdir(parents=True)

        # No SKILL.md or README.md
        (skill_template / "some-file.txt").write_text("content")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["skills"]) == 1
        assert result["skills"][0].name == "custom-skill"
        assert result["skills"][0].description == ""

    def test_scan_ignores_hidden_directories(self, tmp_path):
        """Test scanning ignores hidden directories in skills."""
        templates_dir = tmp_path / "templates"
        skills_dir = templates_dir / "skills"
        skills_dir.mkdir(parents=True)

        # Create hidden directory
        hidden = skills_dir / ".hidden"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("---\nname: hidden\n---")

        # Create normal directory
        normal = skills_dir / "normal"
        normal.mkdir()
        (normal / "SKILL.md").write_text("---\nname: normal\n---")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["skills"]) == 1
        assert result["skills"][0].name == "normal"

    def test_scan_ignores_non_md_files(self, tmp_path):
        """Test scanning ignores non-.md files in agents/rules."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "valid.md").write_text("---\nname: valid\n---")
        (agents_dir / "invalid.txt").write_text("not a template")
        (agents_dir / "also-invalid.yaml").write_text("name: invalid")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        assert len(result["agents"]) == 1
        assert result["agents"][0].name == "valid"

    def test_scan_sorts_by_name(self, tmp_path):
        """Test scan results are sorted by name."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "zebra.md").write_text("---\nname: zebra\n---")
        (agents_dir / "alpha.md").write_text("---\nname: alpha\n---")
        (agents_dir / "middle.md").write_text("---\nname: middle\n---")

        manager = TemplateManager(templates_dir)
        result = manager.scan_templates()

        names = [t.name for t in result["agents"]]
        assert names == ["alpha", "middle", "zebra"]


class TestGetTemplatesByCategory:
    """Test suite for get_templates_by_category method."""

    def test_get_valid_category(self, tmp_path):
        """Test getting templates for valid category."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "test.md").write_text("---\nname: test\n---")

        manager = TemplateManager(templates_dir)
        result = manager.get_templates_by_category("agents")

        assert len(result) == 1
        assert result[0].name == "test"

    def test_get_invalid_category(self, tmp_path):
        """Test getting templates for invalid category returns empty list."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)
        result = manager.get_templates_by_category("invalid")

        assert result == []

    def test_get_empty_category(self, tmp_path):
        """Test getting templates for empty category."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)
        result = manager.get_templates_by_category("agents")

        assert result == []


class TestSearchTemplates:
    """Test suite for search_templates method."""

    def test_search_by_name(self, tmp_path):
        """Test searching templates by name."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: architect\ndescription: Design systems\n---"
        )
        (agents_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Review code\n---"
        )

        manager = TemplateManager(templates_dir)
        result = manager.search_templates("architect")

        assert len(result) == 1
        assert result[0].name == "architect"

    def test_search_by_description(self, tmp_path):
        """Test searching templates by description."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: architect\ndescription: Design systems\n---"
        )
        (agents_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Review code\n---"
        )

        manager = TemplateManager(templates_dir)
        result = manager.search_templates("code")

        assert len(result) == 1
        assert result[0].name == "reviewer"

    def test_search_case_insensitive(self, tmp_path):
        """Test search is case insensitive."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: Architect\ndescription: DESIGN Systems\n---"
        )

        manager = TemplateManager(templates_dir)

        # Search with different cases
        result1 = manager.search_templates("architect")
        result2 = manager.search_templates("ARCHITECT")
        result3 = manager.search_templates("design")
        result4 = manager.search_templates("DESIGN")

        assert len(result1) == 1
        assert len(result2) == 1
        assert len(result3) == 1
        assert len(result4) == 1

    def test_search_with_category_filter(self, tmp_path):
        """Test search with category filter."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        rules_dir = templates_dir / "rules"
        agents_dir.mkdir(parents=True)
        rules_dir.mkdir(parents=True)

        (agents_dir / "security.md").write_text(
            "---\nname: security-agent\ndescription: Security specialist\n---"
        )
        (rules_dir / "security.md").write_text(
            "---\nname: security-rules\ndescription: Security guidelines\n---"
        )

        manager = TemplateManager(templates_dir)

        # Search all categories
        all_results = manager.search_templates("security")
        assert len(all_results) == 2

        # Search specific category
        agents_only = manager.search_templates("security", category="agents")
        assert len(agents_only) == 1
        assert agents_only[0].category == "agents"

    def test_search_no_results(self, tmp_path):
        """Test search with no matching results."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: architect\ndescription: Design systems\n---"
        )

        manager = TemplateManager(templates_dir)
        result = manager.search_templates("nonexistent")

        assert result == []

    def test_search_partial_match(self, tmp_path):
        """Test search with partial string match."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "code-reviewer.md").write_text(
            "---\nname: code-reviewer\ndescription: Reviews code quality\n---"
        )

        manager = TemplateManager(templates_dir)

        # Partial matches
        result1 = manager.search_templates("code")
        result2 = manager.search_templates("review")
        result3 = manager.search_templates("quality")

        assert len(result1) == 1
        assert len(result2) == 1
        assert len(result3) == 1


class TestGetTemplate:
    """Test suite for get_template method."""

    def test_get_existing_template(self, tmp_path):
        """Test getting existing template by category and name."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: architect\ndescription: Design systems\n---"
        )

        manager = TemplateManager(templates_dir)
        result = manager.get_template("agents", "architect")

        assert result is not None
        assert result.name == "architect"
        assert result.category == "agents"

    def test_get_nonexistent_template(self, tmp_path):
        """Test getting nonexistent template returns None."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)
        result = manager.get_template("agents", "nonexistent")

        assert result is None

    def test_get_template_wrong_category(self, tmp_path):
        """Test getting template from wrong category returns None."""
        templates_dir = tmp_path / "templates"
        agents_dir = templates_dir / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "architect.md").write_text(
            "---\nname: architect\ndescription: Design systems\n---"
        )

        manager = TemplateManager(templates_dir)
        result = manager.get_template("rules", "architect")

        assert result is None


class TestIntegrationWithRealTemplates:
    """Integration tests with actual templates directory."""

    def test_scan_real_templates(self):
        """Test scanning real templates directory."""
        manager = TemplateManager()
        result = manager.scan_templates()

        # Should have all three categories
        assert "agents" in result
        assert "rules" in result
        assert "skills" in result

        # Should have some templates in each category
        assert len(result["agents"]) > 0
        assert len(result["rules"]) > 0
        assert len(result["skills"]) > 0

    def test_real_template_has_metadata(self):
        """Test real templates have proper metadata."""
        manager = TemplateManager()
        templates = manager.get_templates_by_category("agents")

        # Find architect template
        architect = next((t for t in templates if t.name == "architect"), None)

        assert architect is not None
        assert architect.description != ""
        assert architect.path.exists()

    def test_search_real_templates(self):
        """Test searching real templates."""
        manager = TemplateManager()

        # Search for common term
        results = manager.search_templates("security")

        assert len(results) > 0
        for template in results:
            assert (
                "security" in template.name.lower()
                or "security" in template.description.lower()
            )
