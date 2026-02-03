"""Interactive template selection UI for ar-sync.

This module provides the TemplateSelector class for interactive
template selection using Rich library components and questionary for fuzzy search.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import questionary
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from ar_sync.template_manager import TemplateManager
from ar_sync.template_models import TemplateMetadata


class TemplateSelector:
    """대화식 템플릿 선택 UI.

    Rich 라이브러리를 사용하여 사용자가 템플릿을 대화식으로
    선택할 수 있는 UI를 제공합니다.

    Attributes:
        template_manager: 템플릿 메타데이터 관리자
        console: Rich Console 인스턴스
    """

    CATEGORY_DESCRIPTIONS = {
        "agents": "AI 에이전트 역할 정의 템플릿",
        "rules": "코딩 규칙 및 가이드라인 템플릿",
        "skills": "특수 기능 스킬 템플릿",
    }

    def __init__(
        self,
        template_manager: TemplateManager,
        console: Console | None = None,
    ) -> None:
        """초기화.

        Args:
            template_manager: 템플릿 메타데이터 관리자
            console: Rich Console 인스턴스. None이면 새로 생성.
        """
        self.template_manager = template_manager
        self.console = console or Console()

    def select_categories(self) -> list[str]:
        """카테고리 선택 UI (fuzzy search with arrow keys).

        Requirement 2.1: 카테고리 목록을 체크박스 형태로 표시

        Returns:
            선택된 카테고리 목록. 취소 시 빈 리스트.
        """
        self.console.print("\n[bold cyan]📁 템플릿 카테고리 선택[/bold cyan]")
        self.console.print("[dim]복사할 템플릿 카테고리를 선택하세요.[/dim]")
        self.console.print(
            "[dim]Use arrow keys to navigate, space to select, enter to confirm[/dim]\n"
        )

        # 카테고리 정보 수집
        all_templates = self.template_manager.scan_templates()
        categories = TemplateManager.CATEGORIES

        # questionary.checkbox로 fuzzy search + arrow key navigation
        choices = []
        for category in categories:
            count = len(all_templates.get(category, []))
            description = self.CATEGORY_DESCRIPTIONS.get(category, "")
            title = f"{category} - {description} ({count} templates)"
            choices.append(Choice(title=title, value=category))

        try:
            selected_categories = questionary.checkbox(
                "Select template categories:",
                choices=choices,
            ).ask()
        except (KeyboardInterrupt, EOFError, OSError):
            # KeyboardInterrupt: User pressed Ctrl+C
            # EOFError: stdin closed (e.g., in tests)
            # OSError: stdin not available (e.g., pytest capture)
            self.console.print("\n[yellow]선택이 취소되었습니다.[/yellow]")
            return []

        # 선택 취소 또는 빈 선택
        if selected_categories is None or not selected_categories:
            self.console.print("[yellow]선택된 카테고리가 없습니다.[/yellow]")
            return []

        # Type narrowing: questionary returns list[Any], but we know it's list[str]
        return list(selected_categories)

    def select_templates(
        self,
        category: str,
        search_query: str | None = None,
    ) -> list[TemplateMetadata]:
        """특정 카테고리에서 템플릿 선택 UI (fuzzy search with arrow keys).

        Requirements:
        - 2.2: 템플릿 목록을 다중 선택 가능한 형태로 표시
        - 2.3: 각 템플릿의 이름과 설명을 함께 표시

        Args:
            category: 템플릿 카테고리
            search_query: 검색어 (None이면 전체 표시)

        Returns:
            선택된 템플릿 목록. 취소 시 빈 리스트.
        """
        # 템플릿 목록 가져오기
        if search_query:
            templates = self.template_manager.search_templates(search_query, category)
        else:
            templates = self.template_manager.get_templates_by_category(category)

        if not templates:
            if search_query:
                self.console.print(
                    f"[yellow]'{search_query}' 검색 결과가 없습니다 ({category}).[/yellow]"
                )
            else:
                self.console.print(f"[yellow]{category} 카테고리에 템플릿이 없습니다.[/yellow]")
            return []

        # 카테고리 헤더
        self.console.print(f"\n[bold cyan]📄 {category.upper()} 템플릿 선택[/bold cyan]")
        if search_query:
            self.console.print(f"[dim]검색어: '{search_query}'[/dim]")
        self.console.print(
            "[dim]Use arrow keys to navigate, space to select, enter to confirm[/dim]\n"
        )

        # questionary.checkbox로 fuzzy search + arrow key navigation
        choices = [
            Choice(
                title=f"{t.display_name} - {t.short_description or 'No description'}",
                value=t.name,
            )
            for t in templates
        ]

        try:
            selected_names = questionary.checkbox(
                f"Select {category} templates:",
                choices=choices,
            ).ask()
        except (KeyboardInterrupt, EOFError, OSError):
            # KeyboardInterrupt: User pressed Ctrl+C
            # EOFError: stdin closed (e.g., in tests)
            # OSError: stdin not available (e.g., pytest capture)
            self.console.print("\n[yellow]선택이 취소되었습니다.[/yellow]")
            return []

        # 선택 취소 또는 빈 선택
        if selected_names is None or not selected_names:
            return []

        # 선택된 이름으로 TemplateMetadata 객체 찾기
        selected: list[TemplateMetadata] = []
        for template in templates:
            if template.name in selected_names:
                selected.append(template)

        return selected

    def confirm_selection(self, selected: list[TemplateMetadata]) -> bool:
        """선택 확인 UI. 사용자가 확인하면 True.

        Requirement 2.4: 선택된 템플릿 목록을 확인 메시지와 함께 표시

        Args:
            selected: 선택된 템플릿 목록

        Returns:
            사용자가 확인하면 True, 취소하면 False
        """
        if not selected:
            self.console.print("[yellow]선택된 템플릿이 없습니다.[/yellow]")
            return False

        # 선택 요약 표시
        self.console.print("\n[bold cyan]📋 선택된 템플릿 확인[/bold cyan]")

        # 카테고리별로 그룹화
        by_category: dict[str, list[TemplateMetadata]] = {}
        for template in selected:
            if template.category not in by_category:
                by_category[template.category] = []
            by_category[template.category].append(template)

        # 테이블로 표시
        table = Table(show_header=True, header_style="bold")
        table.add_column("카테고리", style="cyan")
        table.add_column("템플릿", style="white")

        for category in TemplateManager.CATEGORIES:
            if category in by_category:
                templates = by_category[category]
                names = ", ".join(t.display_name for t in templates)
                table.add_row(category, names)

        self.console.print(table)
        self.console.print(f"\n[bold]총 {len(selected)}개 템플릿이 선택되었습니다.[/bold]")

        # 확인
        try:
            return Confirm.ask(
                "\n[bold]이 템플릿들을 복사하시겠습니까?[/bold]",
                default=True,
                console=self.console,
            )
        except KeyboardInterrupt:
            self.console.print("\n[yellow]작업이 취소되었습니다.[/yellow]")
            return False

    def run_interactive_selection(
        self,
        categories: list[str] | None = None,
        search_query: str | None = None,
    ) -> list[TemplateMetadata]:
        """전체 대화식 선택 플로우 실행.

        Requirements:
        - 2.1-2.6: 전체 대화식 플로우

        Args:
            categories: 미리 선택된 카테고리 (None이면 선택 UI 표시)
            search_query: 검색어 (None이면 전체 표시)

        Returns:
            최종 선택된 템플릿 목록. 취소 시 빈 리스트.
        """
        # 환영 메시지
        self.console.print(
            Panel(
                "[bold]ar-sync 템플릿 초기화[/bold]\n\n"
                "AI IDE 설정을 위한 템플릿을 선택합니다.\n"
                "agents, rules, skills 카테고리에서 필요한 템플릿을 선택하세요.",
                title="🚀 Interactive Template Init",
                border_style="cyan",
            )
        )

        # 카테고리 선택
        if categories is None:
            categories = self.select_categories()

        if not categories:
            # Requirement 2.6: 취소 시 적절한 메시지 표시
            self.console.print("\n[yellow]템플릿 선택이 취소되었습니다.[/yellow]")
            return []

        # 각 카테고리에서 템플릿 선택
        all_selected: list[TemplateMetadata] = []

        for category in categories:
            selected = self.select_templates(category, search_query)
            all_selected.extend(selected)

        if not all_selected:
            self.console.print("\n[yellow]선택된 템플릿이 없습니다.[/yellow]")
            return []

        # 선택 확인
        if not self.confirm_selection(all_selected):
            # Requirement 2.6: 취소 시 적절한 메시지 표시
            self.console.print("\n[yellow]템플릿 복사가 취소되었습니다.[/yellow]")
            return []

        return all_selected
