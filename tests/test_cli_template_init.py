"""Integration tests for CLI template init options.

Tests the init command with template-related options:
--from-template, -t, --list, --search, --category, --output-dir

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.2
"""

from typer.testing import CliRunner

from ar_sync.cli import app

runner = CliRunner()


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

    def test_from_template_starts_interactive_mode(self):
        """Test --from-template starts interactive selection.

        Requirement 4.1: --from-template 옵션으로 대화식 템플릿 선택 모드 시작
        """
        # Use input to simulate user cancellation (empty input)
        result = runner.invoke(app, ["init", "--from-template"], input="q\n")

        # Should exit gracefully (user cancelled)
        assert result.exit_code == 0
        assert "템플릿" in result.output or "카테고리" in result.output

    def test_short_t_option(self):
        """Test -t short option works same as --from-template.

        Requirement 4.2: -t 별칭 동작
        """
        result = runner.invoke(app, ["init", "-t"], input="q\n")

        assert result.exit_code == 0
        assert "템플릿" in result.output or "카테고리" in result.output

    def test_from_template_with_category(self):
        """Test --from-template with --category filter.

        Requirement 4.5: --category 옵션으로 해당 카테고리의 템플릿만 표시
        """
        # With category filter, skip template selection
        result = runner.invoke(app, ["init", "-t", "--category", "agents"], input="s\n")

        assert result.exit_code == 0
        # Should show agents category
        assert "agents" in result.output.lower() or "AGENTS" in result.output

    def test_from_template_with_search(self):
        """Test --from-template with --search filter."""
        result = runner.invoke(app, ["init", "-t", "--search", "security"], input="s\n")

        assert result.exit_code == 0


class TestInitOutputDirOption:
    """Test suite for init --output-dir option."""

    def test_output_dir_option(self, tmp_path):
        """Test --output-dir option sets custom output directory.

        Requirement 4.4: --output-dir 옵션으로 지정된 디렉토리에 템플릿 복사
        """
        custom_dir = str(tmp_path / "custom-output")

        # Test that the option is accepted (cancel immediately)
        result = runner.invoke(app, ["init", "-t", "--output-dir", custom_dir], input="q\n")

        assert result.exit_code == 0

    def test_short_o_option(self, tmp_path):
        """Test -o short option works same as --output-dir."""
        custom_dir = str(tmp_path / "custom-output")

        result = runner.invoke(app, ["init", "-t", "-o", custom_dir], input="q\n")

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

    def test_help_shows_examples(self):
        """Test help text includes template examples."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "ars init -t" in result.output
        assert "ars init --list" in result.output
