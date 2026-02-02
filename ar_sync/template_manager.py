"""Template metadata management for ar-sync.

This module provides the TemplateManager class for scanning, parsing,
and managing template files with YAML frontmatter.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.3
"""

import re
from pathlib import Path

import yaml

from ar_sync.errors import ARSyncError, ErrorCategory
from ar_sync.template_models import TemplateMetadata


class TemplateManager:
    """템플릿 메타데이터 관리자.

    templates 디렉토리에서 템플릿 파일을 스캔하고 메타데이터를 관리합니다.
    YAML frontmatter를 파싱하여 name, description 등의 정보를 추출합니다.

    Attributes:
        CATEGORIES: 지원하는 템플릿 카테고리 목록
        templates_dir: 템플릿 디렉토리 경로
    """

    CATEGORIES = ["agents", "rules", "skills"]

    def __init__(self, templates_dir: Path | None = None) -> None:
        """초기화. templates_dir이 None이면 패키지 내장 템플릿 사용.

        Args:
            templates_dir: 템플릿 디렉토리 경로. None이면 패키지 내장 템플릿 사용.

        Raises:
            ARSyncError: templates 디렉토리가 존재하지 않을 때
        """
        if templates_dir is None:
            # 패키지 내장 템플릿 디렉토리 사용
            package_dir = Path(__file__).parent.parent
            templates_dir = package_dir / "templates"

        self.templates_dir = templates_dir

        if not self.templates_dir.exists():
            raise ARSyncError(
                f"Templates directory not found: {self.templates_dir}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "Ensure ar-sync is properly installed",
                    "Check if templates/ directory exists in the package",
                ],
            )

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
        """YAML frontmatter 파싱.

        파일 내용에서 YAML frontmatter를 추출하고 파싱합니다.
        frontmatter는 파일 시작 부분의 '---'로 둘러싸인 YAML 블록입니다.

        Args:
            content: 파일 전체 내용

        Returns:
            (metadata_dict, body) 튜플.
            frontmatter가 없으면 빈 dict와 원본 content 반환.
        """
        # frontmatter 패턴: 파일 시작의 ---로 둘러싸인 YAML 블록
        # 빈 frontmatter (---\n---) 도 처리
        pattern = r"^---[ \t]*\n(.*?)^---[ \t]*\n?"
        match = re.match(pattern, content, re.DOTALL | re.MULTILINE)

        if not match:
            return {}, content

        frontmatter_text = match.group(1).strip()
        body = content[match.end() :]

        if not frontmatter_text:
            return {}, body

        try:
            metadata = yaml.safe_load(frontmatter_text)
            if metadata is None:
                metadata = {}
        except yaml.YAMLError:
            # YAML 파싱 실패 시 빈 dict 반환
            metadata = {}

        return metadata, body

    def _load_template_metadata(
        self, path: Path, category: str
    ) -> TemplateMetadata | None:
        """단일 템플릿의 메타데이터를 로드.

        Args:
            path: 템플릿 파일 또는 디렉토리 경로
            category: 템플릿 카테고리

        Returns:
            TemplateMetadata 객체. 로드 실패 시 None.
        """
        is_directory = path.is_dir()

        if is_directory:
            # skills 카테고리: 디렉토리 내 SKILL.md 또는 README.md 파일에서 메타데이터 추출
            skill_file = path / "SKILL.md"
            readme_file = path / "README.md"

            if skill_file.exists():
                content_file = skill_file
            elif readme_file.exists():
                content_file = readme_file
            else:
                # 메타데이터 파일이 없으면 디렉토리명 사용
                return TemplateMetadata(
                    name=path.name,
                    description="",
                    category=category,
                    path=path,
                    is_directory=True,
                )

            try:
                content = content_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # 파일 읽기 실패 시 디렉토리명 사용
                return TemplateMetadata(
                    name=path.name,
                    description="",
                    category=category,
                    path=path,
                    is_directory=True,
                )
        else:
            # 파일 템플릿
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # 파일 읽기 실패 시 None 반환 (건너뛰기)
                return None

        metadata, _ = self.parse_frontmatter(content)

        # frontmatter가 없으면 파일명/디렉토리명을 name으로 사용
        name = metadata.get("name", path.stem if not is_directory else path.name)
        description = metadata.get("description", "")

        return TemplateMetadata(
            name=name,
            description=description,
            category=category,
            path=path,
            is_directory=is_directory,
        )

    def scan_templates(self) -> dict[str, list[TemplateMetadata]]:
        """모든 템플릿을 스캔하여 카테고리별로 반환.

        templates 디렉토리의 모든 카테고리를 스캔하고
        각 템플릿의 메타데이터를 로드합니다.

        Returns:
            카테고리를 키로, TemplateMetadata 리스트를 값으로 하는 dict.
            예: {'agents': [...], 'rules': [...], 'skills': [...]}
        """
        result: dict[str, list[TemplateMetadata]] = {
            category: [] for category in self.CATEGORIES
        }

        for category in self.CATEGORIES:
            category_dir = self.templates_dir / category

            if not category_dir.exists():
                continue

            if category == "skills":
                # skills는 디렉토리 형태
                for item in category_dir.iterdir():
                    if item.is_dir() and not item.name.startswith("."):
                        metadata = self._load_template_metadata(item, category)
                        if metadata:
                            result[category].append(metadata)
            else:
                # agents, rules는 파일 형태
                for item in category_dir.iterdir():
                    if item.is_file() and item.suffix == ".md":
                        metadata = self._load_template_metadata(item, category)
                        if metadata:
                            result[category].append(metadata)

        # 각 카테고리 내에서 이름순 정렬
        for category in result:
            result[category].sort(key=lambda t: t.name.lower())

        return result

    def get_templates_by_category(self, category: str) -> list[TemplateMetadata]:
        """특정 카테고리의 템플릿 목록 반환.

        Args:
            category: 템플릿 카테고리 ('agents', 'rules', 'skills')

        Returns:
            해당 카테고리의 TemplateMetadata 리스트.
            유효하지 않은 카테고리면 빈 리스트 반환.
        """
        if category not in self.CATEGORIES:
            return []

        all_templates = self.scan_templates()
        return all_templates.get(category, [])

    def search_templates(
        self, query: str, category: str | None = None
    ) -> list[TemplateMetadata]:
        """이름 또는 설명에서 검색어와 일치하는 템플릿 반환.

        대소문자를 구분하지 않고 검색합니다.

        Args:
            query: 검색어
            category: 특정 카테고리로 제한 (None이면 전체 검색)

        Returns:
            검색어가 이름 또는 설명에 포함된 TemplateMetadata 리스트.
        """
        all_templates = self.scan_templates()
        query_lower = query.lower()
        results: list[TemplateMetadata] = []

        categories_to_search = [category] if category else self.CATEGORIES

        for cat in categories_to_search:
            if cat not in all_templates:
                continue

            for template in all_templates[cat]:
                # 대소문자 무시 검색
                if (
                    query_lower in template.name.lower()
                    or query_lower in template.description.lower()
                ):
                    results.append(template)

        # 이름순 정렬
        results.sort(key=lambda t: t.name.lower())
        return results

    def get_template(self, category: str, name: str) -> TemplateMetadata | None:
        """특정 템플릿 메타데이터 반환.

        Args:
            category: 템플릿 카테고리
            name: 템플릿 이름

        Returns:
            일치하는 TemplateMetadata. 없으면 None.
        """
        templates = self.get_templates_by_category(category)

        for template in templates:
            if template.name == name:
                return template

        return None
