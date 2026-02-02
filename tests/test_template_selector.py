"""Unit tests for TemplateSelector.

Tests the TemplateSelector class including category selection,
template selection, and interactive flow with mocked input.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ar_sync.template_manager import TemplateManager
from ar_sync.template_models import TemplateMetadata
from ar_sync.template_selector import TemplateSelector


@pytest.fixture
def template_manager(tmp_path):
    """Create a TemplateManager with test templates."""
    templates_dir = tmp_path / "templates"

    # Create agents
    agents_dir = templates_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "architect.md").write_text(
        "---\nname: architect\ndescription: Software architecture specialist\n---\nContent"
    )
    (agents_dir / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: Code review expert\n---\nContent"
    )

    # Create rules
    rules_dir = templates_dir / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "coding-style.md").write_text(
        "---\nname: coding-style\ndescription: Coding style guidelines\n---\nContent"
    )

    # Create skills
    skills_dir = templates_dir / "skills"
    skill_template = skills_dir / "web-search"
    skill_template.mkdir(parents=True)
    (skill_template / "SKILL.md").write_text(
        "---\nname: web-search\ndescription: Web search capability\n---\nContent"
    )

    return TemplateManager(templates_dir)


@pytest.fixture
def selector(template_manager):
    """Create a TemplateSelector with test template manager."""
    return TemplateSelector(template_manager)


class TestTemplateSelectorInit:
    """Test suite for TemplateSelector initialization."""

    def test_init_with_template_manager(self, template_manager):
        """Test initialization with template manager."""
        selector = TemplateSelector(template_manager)

        assert selector.template_manager is template_manager
        assert selector.console is not None

    def test_init_with_custom_console(self, template_manager):
        """Test initialization with custom console."""
        from rich.console import Console

        console = Console()
        selector = TemplateSelector(template_manager, console=console)

        assert selector.console is console


class TestSelectCategories:
    """Test suite for select_categories method."""

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_all_categories(self, mock_ask, selector):
        """Test selecting all categories with 'all' input.

        Requirement 2.1: 카테고리 목록을 체크박스 형태로 표시
        """
        mock_ask.return_value = "all"

        result = selector.select_categories()

        assert result == ["agents", "rules", "skills"]

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_specific_categories(self, mock_ask, selector):
        """Test selecting specific categories by number."""
        mock_ask.return_value = "1,3"

        result = selector.select_categories()

        assert result == ["agents", "skills"]

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_single_category(self, mock_ask, selector):
        """Test selecting a single category."""
        mock_ask.return_value = "2"

        result = selector.select_categories()

        assert result == ["rules"]

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_cancel_with_empty_input(self, mock_ask, selector):
        """Test cancellation with empty input.

        Requirement 2.6: 취소 시 적절한 메시지 표시
        """
        mock_ask.return_value = ""

        result = selector.select_categories()

        assert result == []

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_cancel_with_q(self, mock_ask, selector):
        """Test cancellation with 'q' input."""
        mock_ask.return_value = "q"

        result = selector.select_categories()

        assert result == []

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_invalid_input(self, mock_ask, selector):
        """Test handling of invalid input."""
        mock_ask.return_value = "invalid"

        result = selector.select_categories()

        assert result == []


class TestSelectTemplates:
    """Test suite for select_templates method."""

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_all_templates(self, mock_ask, selector):
        """Test selecting all templates in a category.

        Requirement 2.2: 템플릿 목록을 다중 선택 가능한 형태로 표시
        """
        mock_ask.return_value = "all"

        result = selector.select_templates("agents")

        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"architect", "reviewer"}

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_specific_templates(self, mock_ask, selector):
        """Test selecting specific templates by number."""
        mock_ask.return_value = "1"

        result = selector.select_templates("agents")

        assert len(result) == 1
        assert result[0].name == "architect"

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_multiple_templates(self, mock_ask, selector):
        """Test selecting multiple templates."""
        mock_ask.return_value = "1,2"

        result = selector.select_templates("agents")

        assert len(result) == 2

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_skip_category(self, mock_ask, selector):
        """Test skipping a category with 's' input."""
        mock_ask.return_value = "s"

        result = selector.select_templates("agents")

        assert result == []

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_skip_with_empty_input(self, mock_ask, selector):
        """Test skipping with empty input."""
        mock_ask.return_value = ""

        result = selector.select_templates("agents")

        assert result == []

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_select_with_search_query(self, mock_ask, selector):
        """Test selecting templates with search filter."""
        mock_ask.return_value = "all"

        result = selector.select_templates("agents", search_query="architect")

        assert len(result) == 1
        assert result[0].name == "architect"

    def test_empty_category(self, template_manager):
        """Test selecting from empty category."""
        # Create selector with manager that has empty rules
        selector = TemplateSelector(template_manager)

        # Search for non-existent term
        result = selector.select_templates("agents", search_query="nonexistent")

        assert result == []


class TestConfirmSelection:
    """Test suite for confirm_selection method."""

    @patch('ar_sync.template_selector.Confirm.ask')
    def test_confirm_selection(self, mock_confirm, selector):
        """Test confirming selection.

        Requirement 2.4: 선택된 템플릿 목록을 확인 메시지와 함께 표시
        """
        mock_confirm.return_value = True

        templates = [
            TemplateMetadata(
                name="test",
                description="Test template",
                category="agents",
                path=Path("/test.md"),
                is_directory=False,
            ),
        ]

        result = selector.confirm_selection(templates)

        assert result is True

    @patch('ar_sync.template_selector.Confirm.ask')
    def test_cancel_selection(self, mock_confirm, selector):
        """Test cancelling selection.

        Requirement 2.6: 취소 시 적절한 메시지 표시
        """
        mock_confirm.return_value = False

        templates = [
            TemplateMetadata(
                name="test",
                description="Test template",
                category="agents",
                path=Path("/test.md"),
                is_directory=False,
            ),
        ]

        result = selector.confirm_selection(templates)

        assert result is False

    def test_empty_selection(self, selector):
        """Test confirming empty selection returns False."""
        result = selector.confirm_selection([])

        assert result is False

    @patch('ar_sync.template_selector.Confirm.ask')
    def test_confirm_multiple_categories(self, mock_confirm, selector):
        """Test confirming selection from multiple categories."""
        mock_confirm.return_value = True

        templates = [
            TemplateMetadata(
                name="agent1",
                description="Agent 1",
                category="agents",
                path=Path("/agent1.md"),
                is_directory=False,
            ),
            TemplateMetadata(
                name="rule1",
                description="Rule 1",
                category="rules",
                path=Path("/rule1.md"),
                is_directory=False,
            ),
        ]

        result = selector.confirm_selection(templates)

        assert result is True


class TestRunInteractiveSelection:
    """Test suite for run_interactive_selection method."""

    @patch('ar_sync.template_selector.Confirm.ask')
    @patch('ar_sync.template_selector.Prompt.ask')
    def test_full_interactive_flow(self, mock_prompt, mock_confirm, selector):
        """Test full interactive selection flow."""
        # Category selection -> all, Template selection -> all for each, Confirm -> yes
        mock_prompt.side_effect = ["all", "all", "all", "all"]
        mock_confirm.return_value = True

        result = selector.run_interactive_selection()

        assert len(result) > 0

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_cancel_at_category_selection(self, mock_prompt, selector):
        """Test cancellation at category selection.

        Requirement 2.6: 취소 시 적절한 메시지 표시
        """
        mock_prompt.return_value = "q"

        result = selector.run_interactive_selection()

        assert result == []

    @patch('ar_sync.template_selector.Confirm.ask')
    @patch('ar_sync.template_selector.Prompt.ask')
    def test_cancel_at_confirmation(self, mock_prompt, mock_confirm, selector):
        """Test cancellation at confirmation step."""
        mock_prompt.side_effect = ["1", "all"]  # Select agents, all templates
        mock_confirm.return_value = False

        result = selector.run_interactive_selection()

        assert result == []

    @patch('ar_sync.template_selector.Confirm.ask')
    @patch('ar_sync.template_selector.Prompt.ask')
    def test_with_predefined_categories(self, mock_prompt, mock_confirm, selector):
        """Test with predefined categories (skip category selection)."""
        mock_prompt.return_value = "all"
        mock_confirm.return_value = True

        result = selector.run_interactive_selection(categories=["agents"])

        assert len(result) == 2
        assert all(t.category == "agents" for t in result)

    @patch('ar_sync.template_selector.Confirm.ask')
    @patch('ar_sync.template_selector.Prompt.ask')
    def test_with_search_query(self, mock_prompt, mock_confirm, selector):
        """Test with search query filter."""
        mock_prompt.return_value = "all"
        mock_confirm.return_value = True

        result = selector.run_interactive_selection(
            categories=["agents"],
            search_query="architect",
        )

        assert len(result) == 1
        assert result[0].name == "architect"

    @patch('ar_sync.template_selector.Prompt.ask')
    def test_skip_all_templates(self, mock_prompt, selector):
        """Test skipping all template selections."""
        mock_prompt.side_effect = ["1", "s"]  # Select agents, skip templates

        result = selector.run_interactive_selection()

        assert result == []


class TestIntegrationWithRealTemplates:
    """Integration tests with actual templates directory."""

    @patch('ar_sync.template_selector.Confirm.ask')
    @patch('ar_sync.template_selector.Prompt.ask')
    def test_real_templates_selection(self, mock_prompt, mock_confirm):
        """Test selection with real templates."""
        manager = TemplateManager()
        selector = TemplateSelector(manager)

        mock_prompt.side_effect = ["1", "1"]  # Select agents, first template
        mock_confirm.return_value = True

        result = selector.run_interactive_selection()

        assert len(result) == 1
        assert result[0].category == "agents"
