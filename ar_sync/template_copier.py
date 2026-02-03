"""Template copying functionality for ar-sync.

This module provides the TemplateCopier class for copying selected templates
to the target directory with conflict detection and progress display.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.3
"""

import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from ar_sync.errors import ARSyncError, ErrorCategory
from ar_sync.template_manager import TemplateManager
from ar_sync.template_models import CopyResult, TemplateMetadata


class TemplateCopier:
    """템플릿 복사 관리자.

    선택된 템플릿을 대상 디렉토리에 복사하고 충돌을 감지/해결합니다.
    Rich Progress 컴포넌트를 사용하여 진행 상황을 표시합니다.

    Attributes:
        DEFAULT_OUTPUT_DIR: 기본 출력 디렉토리 (.claude)
        output_dir: 템플릿이 복사될 대상 디렉토리
        console: Rich Console 인스턴스
    """

    DEFAULT_OUTPUT_DIR = ".prompts"

    def __init__(
        self,
        output_dir: Path | None = None,
        console: Console | None = None,
    ) -> None:
        """초기화. output_dir이 None이면 DEFAULT_OUTPUT_DIR 사용.

        Args:
            output_dir: 템플릿이 복사될 대상 디렉토리. None이면 기본값 사용.
            console: Rich Console 인스턴스. None이면 새로 생성.
        """
        if output_dir is None:
            self.output_dir = Path.cwd() / self.DEFAULT_OUTPUT_DIR
        else:
            self.output_dir = output_dir

        self.console = console or Console()

    def _ensure_output_dir(self) -> None:
        """출력 디렉토리가 존재하지 않으면 생성.

        Requirement 3.3: 대상 디렉토리가 존재하지 않으면 자동 생성
        """
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def expand_full_set(
        self,
        template: TemplateMetadata,
        manager: TemplateManager,
    ) -> list[TemplateMetadata]:
        """Expand full-set template to include all individual agents.

        When "Full Agent Set" template is selected, this method returns
        all individual agent templates from the agents/ directory,
        excluding the full-set template itself.

        Args:
            template: The full-set template metadata
            manager: TemplateManager instance for scanning templates

        Returns:
            List of all individual agent templates
        """
        if template.name != "Full Agent Set":
            return [template]

        # Get all agents from manager
        all_agents = manager.get_templates_by_category("agents")

        # Filter out the full-set template itself
        individual_agents = [t for t in all_agents if t.name != "Full Agent Set"]

        return individual_agents

    def _get_target_path(self, template: TemplateMetadata) -> Path:
        """템플릿의 대상 경로를 계산.

        Args:
            template: 템플릿 메타데이터

        Returns:
            대상 디렉토리 내의 템플릿 경로
        """
        # 카테고리별 하위 디렉토리 사용
        category_dir = self.output_dir / template.category

        if template.is_directory:
            # skills 카테고리: 디렉토리 전체 복사
            return category_dir / template.path.name
        else:
            # agents, rules 카테고리: 파일 복사
            return category_dir / template.path.name

    def check_conflicts(
        self,
        templates: list[TemplateMetadata],
    ) -> list[TemplateMetadata]:
        """충돌하는 템플릿 목록 반환 (이미 존재하는 파일).

        Requirement 3.4: 동일한 이름의 파일이 이미 존재할 때 감지

        Args:
            templates: 확인할 템플릿 목록

        Returns:
            대상 경로에 이미 파일이 존재하는 템플릿 목록
        """
        conflicts: list[TemplateMetadata] = []

        for template in templates:
            target_path = self._get_target_path(template)
            if target_path.exists():
                conflicts.append(template)

        return conflicts

    def resolve_conflicts(
        self,
        conflicts: list[TemplateMetadata],
    ) -> tuple[list[TemplateMetadata], list[TemplateMetadata]]:
        """충돌 해결 UI. (덮어쓸 목록, 건너뛸 목록) 반환.

        Requirement 3.4: 사용자에게 덮어쓰기 여부 확인

        Args:
            conflicts: 충돌하는 템플릿 목록

        Returns:
            (덮어쓸 템플릿 목록, 건너뛸 템플릿 목록) 튜플
        """
        if not conflicts:
            return [], []

        overwrite: list[TemplateMetadata] = []
        skip: list[TemplateMetadata] = []

        self.console.print("\n[yellow]⚠️  다음 파일이 이미 존재합니다:[/yellow]")

        # 충돌 목록 표시
        table = Table(show_header=True, header_style="bold")
        table.add_column("카테고리", style="cyan")
        table.add_column("템플릿", style="white")
        table.add_column("대상 경로", style="dim")

        for template in conflicts:
            target_path = self._get_target_path(template)
            table.add_row(
                template.category,
                template.display_name,
                str(
                    target_path.relative_to(Path.cwd())
                    if target_path.is_relative_to(Path.cwd())
                    else target_path
                ),
            )

        self.console.print(table)

        # 전체 덮어쓰기 여부 확인
        if len(conflicts) > 1:
            overwrite_all = Confirm.ask(
                "\n[bold]모든 파일을 덮어쓰시겠습니까?[/bold]",
                default=False,
                console=self.console,
            )

            if overwrite_all:
                return conflicts, []

            skip_all = Confirm.ask(
                "[bold]모든 파일을 건너뛰시겠습니까?[/bold]",
                default=False,
                console=self.console,
            )

            if skip_all:
                return [], conflicts

        # 개별 확인
        self.console.print("\n[dim]각 파일에 대해 개별적으로 확인합니다:[/dim]")

        for template in conflicts:
            target_path = self._get_target_path(template)
            should_overwrite = Confirm.ask(
                f"  [cyan]{template.category}/{template.path.name}[/cyan] 덮어쓰기?",
                default=False,
                console=self.console,
            )

            if should_overwrite:
                overwrite.append(template)
            else:
                skip.append(template)

        return overwrite, skip

    def copy_single_template(
        self,
        template: TemplateMetadata,
        force: bool = False,
    ) -> Path | None:
        """단일 템플릿 복사. 성공 시 대상 경로 반환.

        Requirements:
        - 3.1: 선택된 템플릿을 대상 디렉토리에 복사
        - 3.5: skills 카테고리 템플릿은 폴더 전체 복사

        Args:
            template: 복사할 템플릿 메타데이터
            force: True면 기존 파일 덮어쓰기

        Returns:
            성공 시 대상 경로, 실패 시 None

        Raises:
            ARSyncError: 복사 중 오류 발생 시
        """
        target_path = self._get_target_path(template)

        # 대상 파일이 이미 존재하고 force가 아니면 None 반환
        if target_path.exists() and not force:
            return None

        # 카테고리 디렉토리 생성
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if template.is_directory:
                # Requirement 3.5: skills 카테고리는 폴더 전체 복사
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(template.path, target_path)
            else:
                # 파일 복사
                shutil.copy2(template.path, target_path)

            return target_path

        except OSError as e:
            raise ARSyncError(
                f"Failed to copy template: {template.name}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "Check write permissions in the target directory",
                    "Ensure sufficient disk space",
                    f"Error details: {str(e)}",
                ],
            )

    def copy_templates(
        self,
        templates: list[TemplateMetadata],
        force: bool = False,
    ) -> CopyResult:
        """템플릿 복사. force=True면 덮어쓰기.

        Requirements:
        - 3.1: 선택된 템플릿을 대상 디렉토리에 복사
        - 3.3: 대상 디렉토리가 존재하지 않으면 자동 생성
        - 3.6: 복사 완료 시 복사된 파일 목록과 경로 표시
        - 3.7: 복사 중 오류 발생 시 오류 메시지 표시하고 이미 복사된 파일 유지
        - 6.3: Rich Progress 컴포넌트로 진행 상황 표시

        Args:
            templates: 복사할 템플릿 목록
            force: True면 기존 파일 덮어쓰기

        Returns:
            CopyResult 객체 (성공, 건너뜀, 실패 목록 포함)
        """
        if not templates:
            return CopyResult()

        # Expand full-set templates
        expanded_templates: list[TemplateMetadata] = []
        manager = TemplateManager()

        for template in templates:
            if template.name == "Full Agent Set":
                # Expand full-set to all individual agents
                expanded = self.expand_full_set(template, manager)
                expanded_templates.extend(expanded)
            else:
                expanded_templates.append(template)

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_templates: list[TemplateMetadata] = []

        for template in expanded_templates:
            key = f"{template.category}/{template.name}"
            if key not in seen:
                seen.add(key)
                unique_templates.append(template)

        # Requirement 3.3: 대상 디렉토리 자동 생성
        self._ensure_output_dir()

        result = CopyResult()

        # 충돌 확인 및 해결 (force가 아닌 경우)
        if not force:
            conflicts = self.check_conflicts(unique_templates)
            if conflicts:
                overwrite, skip = self.resolve_conflicts(conflicts)

                # 건너뛸 템플릿 처리
                for template in skip:
                    target_path = self._get_target_path(template)
                    result.skipped.append(target_path)

                # 덮어쓸 템플릿은 force=True로 복사
                non_conflict_templates = [t for t in unique_templates if t not in conflicts]
                templates_to_copy = non_conflict_templates + overwrite
                force_for_overwrite = {t.path: True for t in overwrite}
            else:
                templates_to_copy = unique_templates
                force_for_overwrite = {}
        else:
            templates_to_copy = unique_templates
            force_for_overwrite = {}

        # Requirement 6.3: Rich Progress로 진행 상황 표시
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                "[cyan]템플릿 복사 중...",
                total=len(templates_to_copy),
            )

            for template in templates_to_copy:
                progress.update(
                    task,
                    description=f"[cyan]복사 중: {template.category}/{template.name}",
                )

                try:
                    # 개별 템플릿에 대한 force 여부 결정
                    should_force = force or force_for_overwrite.get(template.path, False)
                    target_path_result = self.copy_single_template(template, force=should_force)

                    if target_path_result:
                        result.success.append(target_path_result)
                    else:
                        # 이미 존재하고 force가 아닌 경우 (이론적으로 여기 도달하지 않음)
                        target_path_fallback = self._get_target_path(template)
                        result.skipped.append(target_path_fallback)

                except ARSyncError as e:
                    # Requirement 3.7: 오류 발생 시 오류 메시지 표시하고 계속 진행
                    target_path = self._get_target_path(template)
                    result.failed.append((target_path, e.message))
                    self.console.print(f"[red]✗ {template.name}: {e.message}[/red]")

                progress.advance(task)

        # Requirement 3.6: 복사 완료 시 결과 표시
        self._display_copy_result(result)

        return result

    def _display_copy_result(self, result: CopyResult) -> None:
        """복사 결과를 표시.

        Requirement 3.6: 복사 완료 시 복사된 파일 목록과 경로 표시

        Args:
            result: 복사 결과 객체
        """
        self.console.print()

        if result.success:
            self.console.print(f"[green]✓ {len(result.success)}개 템플릿 복사 완료:[/green]")
            for path in result.success:
                relative_path = (
                    path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
                )
                self.console.print(f"  [dim]→[/dim] {relative_path}")

        if result.skipped:
            self.console.print(f"\n[yellow]⚠ {len(result.skipped)}개 템플릿 건너뜀:[/yellow]")
            for path in result.skipped:
                relative_path = (
                    path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
                )
                self.console.print(f"  [dim]→[/dim] {relative_path}")

        if result.failed:
            # Requirement 3.7: 오류 메시지 표시
            self.console.print(f"\n[red]✗ {len(result.failed)}개 템플릿 복사 실패:[/red]")
            for path, error in result.failed:
                relative_path = (
                    path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
                )
                self.console.print(f"  [dim]→[/dim] {relative_path}: {error}")

        # 요약
        self.console.print()
        self.console.print(
            f"[bold]총 {result.total_count}개 중 "
            f"[green]{result.success_count}개 성공[/green], "
            f"[yellow]{len(result.skipped)}개 건너뜀[/yellow], "
            f"[red]{len(result.failed)}개 실패[/red][/bold]"
        )

    def generate_agents_md(
        self,
        selected: list[TemplateMetadata],
        project_dir: Path | None = None,
    ) -> None:
        """Generate AGENTS.md from template with selected items.

        Args:
            selected: Selected templates
            project_dir: Project directory (defaults to current directory)
        """
        if project_dir is None:
            project_dir = Path.cwd()

        # Read template
        template_path = Path(__file__).parent.parent / "templates" / "AGENTS.md.template"

        if not template_path.exists():
            self.console.print("[yellow]Warning: AGENTS.md.template not found[/yellow]")
            return

        template_content = template_path.read_text(encoding="utf-8")

        # Group by category
        by_category: dict[str, list[TemplateMetadata]] = {
            "agents": [],
            "rules": [],
            "skills": [],
        }

        for template in selected:
            if template.category in by_category:
                by_category[template.category].append(template)

        # Generate lists
        agents_list = self._format_template_list(by_category["agents"])
        rules_list = self._format_template_list(by_category["rules"])
        skills_list = self._format_template_list(by_category["skills"])

        # Replace placeholders
        content = template_content.replace("{agents_list}", agents_list)
        content = content.replace("{rules_list}", rules_list)
        content = content.replace("{skills_list}", skills_list)
        content = content.replace("{timestamp}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Write AGENTS.md
        agents_md_path = project_dir / "AGENTS.md"
        agents_md_path.write_text(content, encoding="utf-8")

        self.console.print("[green]✓ Generated AGENTS.md[/green]")

    def _format_template_list(self, templates: list[TemplateMetadata]) -> str:
        """Format template list for AGENTS.md.

        Args:
            templates: List of templates

        Returns:
            Formatted markdown list
        """
        if not templates:
            return "*No templates selected*"

        lines = []
        for template in sorted(templates, key=lambda t: t.name):
            desc = template.short_description or template.description or "No description"
            lines.append(f"- **{template.display_name}**: {desc}")

        return "\n".join(lines)

    def update_gitignore(
        self,
        project_dir: Path | None = None,
        add_prompts: bool = False,
    ) -> None:
        """Add .prompts/ to .gitignore if requested.

        Args:
            project_dir: Project directory (defaults to current directory)
            add_prompts: If True, add .prompts/ to .gitignore
        """
        if not add_prompts:
            return

        if project_dir is None:
            project_dir = Path.cwd()

        gitignore_path = project_dir / ".gitignore"

        # Read existing .gitignore
        if gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
            lines = content.splitlines()
        else:
            lines = []

        # Check if .prompts/ already exists
        if any(line.strip() in [".prompts/", ".prompts", "AGENTS.md"] for line in lines):
            self.console.print("[dim].prompts/ already in .gitignore[/dim]")
            return

        # Add .prompts/ and AGENTS.md
        lines.append("")
        lines.append("# AI IDE configuration (ar-sync)")
        lines.append(".prompts/")
        lines.append("AGENTS.md")

        # Write back
        gitignore_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.console.print("[green]✓ Added .prompts/ to .gitignore[/green]")
