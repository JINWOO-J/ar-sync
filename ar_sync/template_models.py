"""Data models for template management.

This module defines the data structures used for template initialization:
- TemplateMetadata: Template metadata including name, description, category
- CopyResult: Result of template copy operations

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TemplateMetadata:
    """템플릿 메타데이터 모델.

    Attributes:
        name: 템플릿 이름 (frontmatter 또는 파일명)
        description: 템플릿 설명 (frontmatter 또는 빈 문자열)
        category: 카테고리: 'agents', 'rules', 'skills'
        path: 템플릿 파일/디렉토리 경로
        is_directory: skills는 디렉토리
    """

    name: str
    description: str
    category: str
    path: Path
    is_directory: bool

    @property
    def display_name(self) -> str:
        """UI 표시용 이름.

        Returns:
            하이픈을 공백으로 변환하고 Title Case로 변환된 이름
        """
        return self.name.replace("-", " ").title()

    @property
    def short_description(self) -> str:
        """UI 표시용 짧은 설명 (50자 제한).

        Returns:
            50자 이하면 원본, 초과시 47자 + '...'
        """
        if len(self.description) <= 50:
            return self.description
        return self.description[:47] + "..."


@dataclass
class CopyResult:
    """복사 작업 결과 모델.

    Attributes:
        success: 성공적으로 복사된 파일 경로 목록
        skipped: 건너뛴 파일 경로 목록 (사용자 선택)
        failed: 실패한 파일과 오류 메시지 튜플 목록
    """

    success: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """전체 처리된 항목 수.

        Returns:
            성공 + 건너뜀 + 실패 항목의 총 개수
        """
        return len(self.success) + len(self.skipped) + len(self.failed)

    @property
    def success_count(self) -> int:
        """성공적으로 복사된 항목 수.

        Returns:
            성공 항목의 개수
        """
        return len(self.success)

    @property
    def has_failures(self) -> bool:
        """실패한 항목이 있는지 여부.

        Returns:
            실패 항목이 하나라도 있으면 True
        """
        return len(self.failed) > 0
