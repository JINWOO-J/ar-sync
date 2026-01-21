.PHONY: help install install-dev test test-cov test-verbose lint type-check format clean build publish publish-test run version-bump version-patch version-minor version-major

# 기본 타겟
help:
	@echo "ar-sync Makefile Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install package in editable mode"
	@echo "  make install-dev      - Install with dev dependencies"
	@echo "  make run ARGS='...'   - Run CLI with arguments"
	@echo "                          Example: make run ARGS='--help'"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run all tests"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make test-verbose     - Run tests with verbose output"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run ruff linter"
	@echo "  make type-check       - Run mypy type checker"
	@echo "  make format           - Format code with ruff"
	@echo ""
	@echo "Version Management:"
	@echo "  make version-patch    - Bump patch version (0.1.0 -> 0.1.1)"
	@echo "  make version-minor    - Bump minor version (0.1.0 -> 0.2.0)"
	@echo "  make version-major    - Bump major version (0.1.0 -> 1.0.0)"
	@echo ""
	@echo "Build & Publish:"
	@echo "  make clean            - Remove build artifacts"
	@echo "  make build            - Build distribution packages"
	@echo "  make publish-test     - Publish to TestPyPI"
	@echo "  make publish          - Publish to PyPI"

# 설치
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# 실행
run:
	@python -m ar_sync.cli $(ARGS)

# 예시: make run ARGS="--help"
# 예시: make run ARGS="status"

# 테스트
test:
	pytest

test-cov:
	pytest --cov=ar_sync --cov-report=term-missing --cov-report=html

test-verbose:
	pytest -v

# 코드 품질
lint:
	ruff check ar_sync/ tests/

type-check:
	mypy --strict ar_sync/

format:
	ruff format ar_sync/ tests/

# 버전 관리
version-bump:
	@echo "Current version: $$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2)"
	@echo "Use: make version-patch, make version-minor, or make version-major"

version-patch:
	@current=$$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d'.' -f1); \
	minor=$$(echo $$current | cut -d'.' -f2); \
	patch=$$(echo $$current | cut -d'.' -f3); \
	new_patch=$$(($$patch + 1)); \
	new_version="$$major.$$minor.$$new_patch"; \
	echo "Bumping version: $$current -> $$new_version"; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" ar_sync/__version__.py; \
	rm -f ar_sync/__version__.py.bak; \
	echo "Version bumped to $$new_version"

version-minor:
	@current=$$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d'.' -f1); \
	minor=$$(echo $$current | cut -d'.' -f2); \
	new_minor=$$(($$minor + 1)); \
	new_version="$$major.$$new_minor.0"; \
	echo "Bumping version: $$current -> $$new_version"; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" ar_sync/__version__.py; \
	rm -f ar_sync/__version__.py.bak; \
	echo "Version bumped to $$new_version"

version-major:
	@current=$$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d'.' -f1); \
	new_major=$$(($$major + 1)); \
	new_version="$$new_major.0.0"; \
	echo "Bumping version: $$current -> $$new_version"; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" ar_sync/__version__.py; \
	rm -f ar_sync/__version__.py.bak; \
	echo "Version bumped to $$new_version"

# 빌드 및 배포
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .hypothesis/
	rm -rf htmlcov/
	rm -f .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

publish-test: verify
	@echo ""
	@echo "Publishing to TestPyPI..."
	@current=$$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2); \
	echo "Version: $$current"; \
	python -m build; \
	python -m twine upload --repository testpypi dist/*

publish: verify
	@echo ""
	@echo "Publishing to PyPI..."
	@current=$$(grep '__version__' ar_sync/__version__.py | cut -d'"' -f2); \
	echo "Version: $$current"; \
	read -p "Are you sure you want to publish version $$current to PyPI? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		python -m build; \
		python -m twine upload dist/*; \
		echo ""; \
		echo "✓ Published version $$current to PyPI"; \
		echo ""; \
		echo "Don't forget to:"; \
		echo "  1. git add ar_sync/__version__.py"; \
		echo "  2. git commit -m 'Bump version to $$current'"; \
		echo "  3. git tag v$$current"; \
		echo "  4. git push && git push --tags"; \
	else \
		echo "Publish cancelled"; \
	fi

# 전체 검증 (CI/CD용)
verify: install-dev lint type-check test-cov
	@echo ""
	@echo "✓ All checks passed!"
