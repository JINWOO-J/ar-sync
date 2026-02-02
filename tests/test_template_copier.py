"""Unit tests for TemplateCopier.

Tests the TemplateCopier class including template copying,
conflict detection, and progress display.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.3
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ar_sync.errors import ARSyncError
from ar_sync.template_copier import TemplateCopier
from ar_sync.template_models import CopyResult, TemplateMetadata


class TestTemplateCopierInit:
    """Test suite for TemplateCopier initialization."""

    def test_init_with_default_output_dir(self, tmp_path, monkeypatch):
        """Test initialization with default output directory.
        
        Requirement 3.2: 기본 대상 디렉토리로 `.claude/` 사용
        """
        monkeypatch.chdir(tmp_path)
        
        copier = TemplateCopier()
        
        assert copier.output_dir == tmp_path / ".claude"

    def test_init_with_custom_output_dir(self, tmp_path):
        """Test initialization with custom output directory."""
        custom_dir = tmp_path / "custom-output"
        
        copier = TemplateCopier(output_dir=custom_dir)
        
        assert copier.output_dir == custom_dir

    def test_default_output_dir_constant(self):
        """Test DEFAULT_OUTPUT_DIR constant value.
        
        Requirement 3.2: 기본 대상 디렉토리로 `.claude/` 사용
        """
        assert TemplateCopier.DEFAULT_OUTPUT_DIR == ".claude"


class TestEnsureOutputDir:
    """Test suite for _ensure_output_dir method."""

    def test_creates_nonexistent_directory(self, tmp_path):
        """Test that nonexistent output directory is created.
        
        Requirement 3.3: 대상 디렉토리가 존재하지 않으면 자동 생성
        """
        output_dir = tmp_path / "new-dir" / "nested"
        copier = TemplateCopier(output_dir=output_dir)
        
        assert not output_dir.exists()
        
        copier._ensure_output_dir()
        
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_existing_directory_unchanged(self, tmp_path):
        """Test that existing directory is not modified."""
        output_dir = tmp_path / "existing"
        output_dir.mkdir()
        (output_dir / "existing-file.txt").write_text("content")
        
        copier = TemplateCopier(output_dir=output_dir)
        copier._ensure_output_dir()
        
        assert output_dir.exists()
        assert (output_dir / "existing-file.txt").exists()


class TestGetTargetPath:
    """Test suite for _get_target_path method."""

    def test_file_template_target_path(self, tmp_path):
        """Test target path calculation for file templates."""
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="architect",
            description="Test",
            category="agents",
            path=Path("/templates/agents/architect.md"),
            is_directory=False,
        )
        
        target = copier._get_target_path(template)
        
        assert target == output_dir / "agents" / "architect.md"

    def test_directory_template_target_path(self, tmp_path):
        """Test target path calculation for directory templates (skills).
        
        Requirement 3.5: skills 카테고리 템플릿은 폴더 전체 복사
        """
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="web-search",
            description="Test",
            category="skills",
            path=Path("/templates/skills/web-search"),
            is_directory=True,
        )
        
        target = copier._get_target_path(template)
        
        assert target == output_dir / "skills" / "web-search"


class TestCheckConflicts:
    """Test suite for check_conflicts method."""

    def test_no_conflicts(self, tmp_path):
        """Test when no conflicts exist."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="test1",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test1.md",
                is_directory=False,
            ),
        ]
        
        conflicts = copier.check_conflicts(templates)
        
        assert conflicts == []

    def test_detects_file_conflict(self, tmp_path):
        """Test detection of existing file conflict.
        
        Requirement 3.4: 동일한 이름의 파일이 이미 존재할 때 감지
        """
        output_dir = tmp_path / "output"
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "existing.md").write_text("existing content")
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="existing",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "existing.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="new",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "new.md",
                is_directory=False,
            ),
        ]
        
        conflicts = copier.check_conflicts(templates)
        
        assert len(conflicts) == 1
        assert conflicts[0].name == "existing"

    def test_detects_directory_conflict(self, tmp_path):
        """Test detection of existing directory conflict.
        
        Requirement 3.5: skills 카테고리 디렉토리 충돌 감지
        """
        output_dir = tmp_path / "output"
        skills_dir = output_dir / "skills" / "existing-skill"
        skills_dir.mkdir(parents=True)
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="existing-skill",
                description="",
                category="skills",
                path=tmp_path / "templates" / "skills" / "existing-skill",
                is_directory=True,
            ),
        ]
        
        conflicts = copier.check_conflicts(templates)
        
        assert len(conflicts) == 1
        assert conflicts[0].name == "existing-skill"

    def test_multiple_conflicts(self, tmp_path):
        """Test detection of multiple conflicts."""
        output_dir = tmp_path / "output"
        agents_dir = output_dir / "agents"
        rules_dir = output_dir / "rules"
        agents_dir.mkdir(parents=True)
        rules_dir.mkdir(parents=True)
        (agents_dir / "agent1.md").write_text("content")
        (rules_dir / "rule1.md").write_text("content")
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="agent1",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "agent1.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="rule1",
                description="",
                category="rules",
                path=tmp_path / "templates" / "rules" / "rule1.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="new-agent",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "new-agent.md",
                is_directory=False,
            ),
        ]
        
        conflicts = copier.check_conflicts(templates)
        
        assert len(conflicts) == 2
        conflict_names = {c.name for c in conflicts}
        assert conflict_names == {"agent1", "rule1"}


class TestCopySingleTemplate:
    """Test suite for copy_single_template method."""

    def test_copy_file_template(self, tmp_path):
        """Test copying a file template.
        
        Requirement 3.1: 선택된 템플릿을 대상 디렉토리에 복사
        """
        # Setup source template
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        source_file = templates_dir / "test.md"
        source_file.write_text("---\nname: test\n---\nContent here.")
        
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="test",
            description="Test template",
            category="agents",
            path=source_file,
            is_directory=False,
        )
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert result == output_dir / "agents" / "test.md"
        assert result.exists()
        assert result.read_text() == source_file.read_text()

    def test_copy_directory_template(self, tmp_path):
        """Test copying a directory template (skills).
        
        Requirement 3.5: skills 카테고리 템플릿은 폴더 전체 복사
        """
        # Setup source skill directory
        templates_dir = tmp_path / "templates" / "skills" / "web-search"
        templates_dir.mkdir(parents=True)
        (templates_dir / "SKILL.md").write_text("---\nname: web-search\n---")
        (templates_dir / "search.py").write_text("# search code")
        
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="web-search",
            description="Web search skill",
            category="skills",
            path=templates_dir,
            is_directory=True,
        )
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert result == output_dir / "skills" / "web-search"
        assert result.is_dir()
        assert (result / "SKILL.md").exists()
        assert (result / "search.py").exists()

    def test_copy_without_force_existing_file(self, tmp_path):
        """Test copying without force when file exists returns None."""
        # Setup source and existing target
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        source_file = templates_dir / "test.md"
        source_file.write_text("new content")
        
        output_dir = tmp_path / "output"
        target_dir = output_dir / "agents"
        target_dir.mkdir(parents=True)
        (target_dir / "test.md").write_text("existing content")
        
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="test",
            description="",
            category="agents",
            path=source_file,
            is_directory=False,
        )
        
        result = copier.copy_single_template(template, force=False)
        
        assert result is None
        # Original file should be unchanged
        assert (target_dir / "test.md").read_text() == "existing content"

    def test_copy_with_force_overwrites(self, tmp_path):
        """Test copying with force overwrites existing file."""
        # Setup source and existing target
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        source_file = templates_dir / "test.md"
        source_file.write_text("new content")
        
        output_dir = tmp_path / "output"
        target_dir = output_dir / "agents"
        target_dir.mkdir(parents=True)
        (target_dir / "test.md").write_text("existing content")
        
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="test",
            description="",
            category="agents",
            path=source_file,
            is_directory=False,
        )
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert (target_dir / "test.md").read_text() == "new content"

    def test_copy_creates_category_directory(self, tmp_path):
        """Test that category directory is created if not exists."""
        templates_dir = tmp_path / "templates" / "rules"
        templates_dir.mkdir(parents=True)
        source_file = templates_dir / "test.md"
        source_file.write_text("content")
        
        output_dir = tmp_path / "output"
        # Don't create output_dir or rules subdirectory
        
        copier = TemplateCopier(output_dir=output_dir)
        
        template = TemplateMetadata(
            name="test",
            description="",
            category="rules",
            path=source_file,
            is_directory=False,
        )
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert (output_dir / "rules").is_dir()
        assert result.exists()


class TestCopyTemplates:
    """Test suite for copy_templates method."""

    def test_copy_empty_list(self, tmp_path):
        """Test copying empty template list."""
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        result = copier.copy_templates([])
        
        assert result.success == []
        assert result.skipped == []
        assert result.failed == []

    def test_copy_multiple_templates(self, tmp_path):
        """Test copying multiple templates.
        
        Requirement 3.1: 선택된 템플릿을 대상 디렉토리에 복사
        """
        # Setup source templates
        agents_dir = tmp_path / "templates" / "agents"
        rules_dir = tmp_path / "templates" / "rules"
        agents_dir.mkdir(parents=True)
        rules_dir.mkdir(parents=True)
        
        (agents_dir / "agent1.md").write_text("agent1 content")
        (agents_dir / "agent2.md").write_text("agent2 content")
        (rules_dir / "rule1.md").write_text("rule1 content")
        
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="agent1",
                description="",
                category="agents",
                path=agents_dir / "agent1.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="agent2",
                description="",
                category="agents",
                path=agents_dir / "agent2.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="rule1",
                description="",
                category="rules",
                path=rules_dir / "rule1.md",
                is_directory=False,
            ),
        ]
        
        result = copier.copy_templates(templates, force=True)
        
        assert len(result.success) == 3
        assert result.success_count == 3
        assert not result.has_failures

    def test_copy_creates_output_directory(self, tmp_path):
        """Test that output directory is created automatically.
        
        Requirement 3.3: 대상 디렉토리가 존재하지 않으면 자동 생성
        """
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        (templates_dir / "test.md").write_text("content")
        
        output_dir = tmp_path / "new-output"
        assert not output_dir.exists()
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="test",
                description="",
                category="agents",
                path=templates_dir / "test.md",
                is_directory=False,
            ),
        ]
        
        copier.copy_templates(templates, force=True)
        
        assert output_dir.exists()

    def test_copy_with_force_skips_conflict_resolution(self, tmp_path):
        """Test that force=True skips conflict resolution."""
        # Setup source and existing target
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        (templates_dir / "test.md").write_text("new content")
        
        output_dir = tmp_path / "output"
        target_dir = output_dir / "agents"
        target_dir.mkdir(parents=True)
        (target_dir / "test.md").write_text("existing content")
        
        copier = TemplateCopier(output_dir=output_dir)
        
        templates = [
            TemplateMetadata(
                name="test",
                description="",
                category="agents",
                path=templates_dir / "test.md",
                is_directory=False,
            ),
        ]
        
        result = copier.copy_templates(templates, force=True)
        
        assert len(result.success) == 1
        assert (target_dir / "test.md").read_text() == "new content"

    def test_partial_failure_preserves_successful_copies(self, tmp_path):
        """Test that partial failure preserves already copied files.
        
        Requirement 3.7: 복사 중 오류 발생 시 이미 복사된 파일 유지
        """
        # Setup source templates
        templates_dir = tmp_path / "templates" / "agents"
        templates_dir.mkdir(parents=True)
        (templates_dir / "good.md").write_text("good content")
        
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        # Create a template with non-existent source (will fail)
        templates = [
            TemplateMetadata(
                name="good",
                description="",
                category="agents",
                path=templates_dir / "good.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="bad",
                description="",
                category="agents",
                path=templates_dir / "nonexistent.md",  # This doesn't exist
                is_directory=False,
            ),
        ]
        
        result = copier.copy_templates(templates, force=True)
        
        # Good template should be copied
        assert len(result.success) == 1
        assert (output_dir / "agents" / "good.md").exists()
        
        # Bad template should be in failed list
        assert len(result.failed) == 1


class TestCopyResult:
    """Test suite for CopyResult dataclass."""

    def test_total_count(self):
        """Test total_count property."""
        result = CopyResult(
            success=[Path("a"), Path("b")],
            skipped=[Path("c")],
            failed=[(Path("d"), "error")],
        )
        
        assert result.total_count == 4

    def test_success_count(self):
        """Test success_count property."""
        result = CopyResult(
            success=[Path("a"), Path("b"), Path("c")],
            skipped=[],
            failed=[],
        )
        
        assert result.success_count == 3

    def test_has_failures_true(self):
        """Test has_failures when there are failures."""
        result = CopyResult(
            success=[],
            skipped=[],
            failed=[(Path("a"), "error")],
        )
        
        assert result.has_failures is True

    def test_has_failures_false(self):
        """Test has_failures when there are no failures."""
        result = CopyResult(
            success=[Path("a")],
            skipped=[Path("b")],
            failed=[],
        )
        
        assert result.has_failures is False


class TestResolveConflicts:
    """Test suite for resolve_conflicts method."""

    def test_empty_conflicts(self, tmp_path):
        """Test resolve_conflicts with empty list."""
        copier = TemplateCopier(output_dir=tmp_path)
        
        overwrite, skip = copier.resolve_conflicts([])
        
        assert overwrite == []
        assert skip == []

    @patch('ar_sync.template_copier.Confirm.ask')
    def test_overwrite_all(self, mock_confirm, tmp_path):
        """Test overwrite all option."""
        mock_confirm.return_value = True  # Yes to "overwrite all"
        
        output_dir = tmp_path / "output"
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "test1.md").touch()
        (agents_dir / "test2.md").touch()
        
        copier = TemplateCopier(output_dir=output_dir)
        
        conflicts = [
            TemplateMetadata(
                name="test1",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test1.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="test2",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test2.md",
                is_directory=False,
            ),
        ]
        
        overwrite, skip = copier.resolve_conflicts(conflicts)
        
        assert len(overwrite) == 2
        assert len(skip) == 0

    @patch('ar_sync.template_copier.Confirm.ask')
    def test_skip_all(self, mock_confirm, tmp_path):
        """Test skip all option."""
        mock_confirm.side_effect = [False, True]  # No to overwrite all, Yes to skip all
        
        output_dir = tmp_path / "output"
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "test1.md").touch()
        (agents_dir / "test2.md").touch()
        
        copier = TemplateCopier(output_dir=output_dir)
        
        conflicts = [
            TemplateMetadata(
                name="test1",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test1.md",
                is_directory=False,
            ),
            TemplateMetadata(
                name="test2",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test2.md",
                is_directory=False,
            ),
        ]
        
        overwrite, skip = copier.resolve_conflicts(conflicts)
        
        assert len(overwrite) == 0
        assert len(skip) == 2

    @patch('ar_sync.template_copier.Confirm.ask')
    def test_single_conflict_direct_prompt(self, mock_confirm, tmp_path):
        """Test single conflict goes directly to individual prompt."""
        mock_confirm.return_value = True  # Yes to overwrite
        
        output_dir = tmp_path / "output"
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "test.md").touch()
        
        copier = TemplateCopier(output_dir=output_dir)
        
        conflicts = [
            TemplateMetadata(
                name="test",
                description="",
                category="agents",
                path=tmp_path / "templates" / "agents" / "test.md",
                is_directory=False,
            ),
        ]
        
        overwrite, skip = copier.resolve_conflicts(conflicts)
        
        # Single conflict should be handled directly
        assert len(overwrite) == 1
        assert len(skip) == 0


class TestIntegrationWithRealTemplates:
    """Integration tests with actual templates directory."""

    def test_copy_real_template(self, tmp_path):
        """Test copying a real template from templates directory."""
        from ar_sync.template_manager import TemplateManager
        
        manager = TemplateManager()
        agents = manager.get_templates_by_category("agents")
        
        if not agents:
            pytest.skip("No agent templates available")
        
        template = agents[0]
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert result.exists()
        
        # Verify content matches
        original_content = template.path.read_text()
        copied_content = result.read_text()
        assert original_content == copied_content

    def test_copy_real_skill_template(self, tmp_path):
        """Test copying a real skill template (directory)."""
        from ar_sync.template_manager import TemplateManager
        
        manager = TemplateManager()
        skills = manager.get_templates_by_category("skills")
        
        if not skills:
            pytest.skip("No skill templates available")
        
        template = skills[0]
        output_dir = tmp_path / "output"
        copier = TemplateCopier(output_dir=output_dir)
        
        result = copier.copy_single_template(template, force=True)
        
        assert result is not None
        assert result.exists()
        assert result.is_dir()
        
        # Verify directory contents
        original_files = set(f.name for f in template.path.iterdir())
        copied_files = set(f.name for f in result.iterdir())
        assert original_files == copied_files
