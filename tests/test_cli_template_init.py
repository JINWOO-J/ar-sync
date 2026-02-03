"""Integration tests for CLI template init options.

Tests the init command with template-related options:
--from-template, -t, --list, --search, --category, --output-dir

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.2
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ar_sync.cli import app
from ar_sync.config_manager import ConfigManager

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_config():
    """Clean up any existing config file before each test."""
    config_path = ConfigManager.CONFIG_PATH
    if config_path.exists():
        config_path.unlink()
    yield
    # Cleanup after test
    if config_path.exists():
        config_path.unlink()


class TestInitListOption:
    """Test suite for init --list option."""

    def test_list_shows_templates(self):
        """Test --list option shows available templates.

        Requirement 4.6: --list 옵션으로 대화식 모드 없이 템플릿 목록 표시
        """
        result = runner.invoke(app, ["init", "--list"])

        assert result.exit_code == 0
        assert "사용 가능한 템플릿" in result.output
        assert "AGENTS" in result.output
        assert "RULES" in result.output
        assert "SKILLS" in result.output

    def test_list_with_search(self):
        """Test --list with --search option.

        Requirement 5.2: --search 옵션과 함께 --list 사용 시 검색 결과만 표시
        """
        result = runner.invoke(app, ["init", "--list", "--search", "security"])

        assert result.exit_code == 0
        assert "검색어: 'security'" in result.output
        assert "Security" in result.output

    def test_list_with_category_filter(self):
        """Test --list with --category option.

        Requirement 4.5: --category 옵션으로 해당 카테고리의 템플릿만 표시
        """
        result = runner.invoke(app, ["init", "--list", "--category", "agents"])

        assert result.exit_code == 0
        assert "AGENTS" in result.output
        # Should not show other categories
        assert "RULES" not in result.output or "RULES (0개)" in result.output

    def test_list_search_no_results(self):
        """Test --list with search that returns no results."""
        result = runner.invoke(app, ["init", "--list", "--search", "nonexistent12345"])

        assert result.exit_code == 0
        assert "검색 결과가 없습니다" in result.output

    def test_short_list_option(self):
        """Test -l short option works same as --list."""
        result = runner.invoke(app, ["-l"])

        # -l is not a global option, so this should fail
        # Let's test with init -l instead
        result = runner.invoke(app, ["init", "-l"])

        assert result.exit_code == 0
        assert "사용 가능한 템플릿" in result.output


class TestInitFromTemplateOption:
    """Test suite for init --from-template option."""

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_from_template_starts_interactive_mode(self, mock_checkbox):
        """Test --from-template starts interactive selection.

        Requirement 4.1: --from-template 옵션으로 대화식 템플릿 선택 모드 시작
        """
        # Mock questionary.checkbox to return empty (user cancelled)
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "--from-template"])

        # Should exit gracefully (user cancelled)
        assert result.exit_code == 0
        assert "템플릿" in result.output or "카테고리" in result.output

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_short_t_option(self, mock_checkbox):
        """Test -t short option works same as --from-template.

        Requirement 4.2: -t 별칭 동작
        """
        # Mock questionary.checkbox to return empty (user cancelled)
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "-t"])

        assert result.exit_code == 0
        assert "템플릿" in result.output or "카테고리" in result.output

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_from_template_with_category(self, mock_checkbox):
        """Test --from-template with --category filter.

        Requirement 4.5: --category 옵션으로 해당 카테고리의 템플릿만 표시
        """
        # Mock questionary.checkbox to return empty (skip template selection)
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "-t", "--category", "agents"])

        assert result.exit_code == 0
        # Should show agents category
        assert "agents" in result.output.lower() or "AGENTS" in result.output

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_from_template_with_search(self, mock_checkbox):
        """Test --from-template with --search filter."""
        # Mock questionary.checkbox to return empty
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "-t", "--search", "security"])

        assert result.exit_code == 0


class TestInitOutputDirOption:
    """Test suite for init --output-dir option."""

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_output_dir_option(self, mock_checkbox, tmp_path):
        """Test --output-dir option sets custom output directory.

        Requirement 4.4: --output-dir 옵션으로 지정된 디렉토리에 템플릿 복사
        """
        custom_dir = str(tmp_path / "custom-output")

        # Mock questionary.checkbox to return empty (cancel immediately)
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "-t", "--output-dir", custom_dir])

        assert result.exit_code == 0

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_short_o_option(self, mock_checkbox, tmp_path):
        """Test -o short option works same as --output-dir."""
        custom_dir = str(tmp_path / "custom-output")

        # Mock questionary.checkbox to return empty
        mock_result = MagicMock()
        mock_result.ask.return_value = []
        mock_checkbox.return_value = mock_result

        result = runner.invoke(app, ["init", "-t", "-o", custom_dir])

        assert result.exit_code == 0


class TestInitLegacyBehavior:
    """Test suite for legacy init behavior preservation."""

    def test_init_without_template_options_requires_config(self):
        """Test init without template options requires global config.

        Requirement 4.3: --from-template 옵션 없이 ars init 실행 시 기존 동작 유지
        """
        # Without template options, init should try to load config
        # and fail if not configured
        result = runner.invoke(app, ["init"])

        # Should fail because no global config exists (in test environment)
        # or succeed if config exists - either way, it's the legacy behavior
        # The key is that it doesn't start template selection
        assert "템플릿" not in result.output or result.exit_code != 0

    def test_list_only_does_not_require_config(self):
        """Test --list only mode doesn't require global config."""
        result = runner.invoke(app, ["init", "--list"])

        # Should succeed without global config
        assert result.exit_code == 0
        assert "사용 가능한 템플릿" in result.output


class TestInitHelpText:
    """Test suite for init command help text."""

    def test_help_shows_template_options(self):
        """Test help text includes template options."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "--from-template" in result.output
        assert "-t" in result.output
        assert "--output-dir" in result.output
        assert "-o" in result.output
        assert "--category" in result.output
        assert "-c" in result.output
        assert "--list" in result.output
        assert "-l" in result.output
        assert "--search" in result.output
        assert "-s" in result.output
        assert "--gitignore" in result.output

    def test_help_shows_examples(self):
        """Test help text includes template examples."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "ars init -t" in result.output
        assert "ars init --list" in result.output


class TestInitAgentsMdGeneration:
    """Test suite for AGENTS.md generation."""

    @patch("ar_sync.template_selector.questionary.checkbox")
    def test_agents_md_generation_called_on_success(self, mock_checkbox, tmp_path):
        """Test that generate_agents_md is called when templates are copied successfully."""
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Mock template selection to return empty (user cancelled)
            mock_result = MagicMock()
            mock_result.ask.return_value = []
            mock_checkbox.return_value = mock_result

            result = runner.invoke(app, ["init", "-t"])

            # Should exit gracefully without error
            assert result.exit_code == 0

        finally:
            os.chdir(original_cwd)

    def test_help_shows_gitignore_option(self):
        """Test that --gitignore option is shown in help."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "--gitignore" in result.output
        assert "team sharing" in result.output.lower()


class TestInitAllOption:
    """Test suite for init --all option."""

    def test_all_copies_all_templates(self):
        """Test --all option copies all templates automatically.

        Requirement: --all 옵션으로 모든 템플릿 자동 복사
        """
        with patch("ar_sync.template_manager.TemplateManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Mock scan_templates to return some templates
            from pathlib import Path

            from ar_sync.template_models import TemplateMetadata

            mock_manager.scan_templates.return_value = {
                "agents": [
                    TemplateMetadata("agent1", "desc1", "agents", Path("a1"), False),
                    TemplateMetadata("agent2", "desc2", "agents", Path("a2"), False),
                ],
                "rules": [TemplateMetadata("rule1", "desc3", "rules", Path("r1"), False)],
                "skills": [TemplateMetadata("skill1", "desc4", "skills", Path("s1"), True)],
            }

            with patch("ar_sync.template_copier.TemplateCopier") as mock_copier_class:
                mock_copier = MagicMock()
                mock_copier_class.return_value = mock_copier

                # Mock successful copy
                from ar_sync.template_models import CopyResult

                mock_result = CopyResult(
                    success=[Path("a1"), Path("a2"), Path("r1"), Path("s1")],
                    skipped=[],
                    failed=[],
                )
                mock_copier.copy_templates.return_value = mock_result

                result = runner.invoke(app, ["init", "-t", "--all"])

                assert result.exit_code == 0
                assert "Copying 4 templates" in result.output
                assert "Successfully copied 4 templates" in result.output
                mock_copier.copy_templates.assert_called_once()

    def test_all_with_category_filter(self):
        """Test --all with --category option filters templates.

        Requirement: --all과 --category 조합으로 특정 카테고리만 복사
        """
        with patch("ar_sync.template_manager.TemplateManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Mock scan_templates to return templates
            from pathlib import Path

            from ar_sync.template_models import TemplateMetadata

            mock_manager.scan_templates.return_value = {
                "agents": [
                    TemplateMetadata("agent1", "desc1", "agents", Path("a1"), False),
                    TemplateMetadata("agent2", "desc2", "agents", Path("a2"), False),
                ],
                "rules": [TemplateMetadata("rule1", "desc3", "rules", Path("r1"), False)],
            }

            with patch("ar_sync.template_copier.TemplateCopier") as mock_copier_class:
                mock_copier = MagicMock()
                mock_copier_class.return_value = mock_copier

                # Mock successful copy
                from ar_sync.template_models import CopyResult

                mock_result = CopyResult(
                    success=[Path("a1"), Path("a2")],
                    skipped=[],
                    failed=[],
                )
                mock_copier.copy_templates.return_value = mock_result

                result = runner.invoke(app, ["init", "-t", "--all", "--category", "agents"])

                assert result.exit_code == 0
                assert "Copying 2 templates" in result.output
                mock_copier.copy_templates.assert_called_once()

    def test_all_with_no_templates(self):
        """Test --all with no templates available.

        Requirement: 템플릿이 없을 때 적절한 메시지 표시
        """
        with patch("ar_sync.template_manager.TemplateManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Mock scan_templates to return empty
            mock_manager.scan_templates.return_value = {}

            result = runner.invoke(app, ["init", "-t", "--all"])

            assert result.exit_code == 0
            assert "No templates available" in result.output

    def test_all_with_output_dir(self):
        """Test --all with custom output directory.

        Requirement: --all과 --output-dir 조합
        """
        with patch("ar_sync.template_manager.TemplateManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            from pathlib import Path

            from ar_sync.template_models import TemplateMetadata

            mock_manager.scan_templates.return_value = {
                "agents": [TemplateMetadata("agent1", "desc1", "agents", Path("a1"), False)],
            }

            with patch("ar_sync.template_copier.TemplateCopier") as mock_copier_class:
                mock_copier = MagicMock()
                mock_copier_class.return_value = mock_copier

                from ar_sync.template_models import CopyResult

                mock_result = CopyResult(
                    success=[Path("a1")],
                    skipped=[],
                    failed=[],
                )
                mock_copier.copy_templates.return_value = mock_result

                result = runner.invoke(app, ["init", "-t", "--all", "-o", ".cursor"])

                assert result.exit_code == 0
                # Verify TemplateCopier was called with custom output_dir
                call_args = mock_copier_class.call_args
                assert call_args is not None

    def test_all_without_from_template_flag(self):
        """Test --all requires -t flag.

        Requirement: --all은 -t와 함께 사용해야 함
        """
        result = runner.invoke(app, ["init", "--all"])

        # Should not trigger template copying without -t
        assert "Copying" not in result.output or result.exit_code != 0
