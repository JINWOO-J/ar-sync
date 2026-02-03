---
name: Full Agent Set
category: agents
description: Complete agent suite for comprehensive AI-assisted development
short_description: All agents for full workflow coverage
version: 1.0.0
---

# Full Agent Set

This is a meta-template that includes all available agents for complete workflow coverage.

## Included Agents

### Core Development
- **planner**: Implementation planning for complex features and refactoring
- **architect**: System design and architectural decisions
- **tdd-guide**: Test-driven development guidance for new features and bug fixes

### Code Quality
- **code-reviewer**: General code review and quality assessment
- **python-reviewer**: Python-specific code review and best practices
- **go-reviewer**: Go-specific code review and best practices
- **database-reviewer**: Database schema and query optimization review
- **security-reviewer**: Security analysis and vulnerability assessment

### Maintenance & Operations
- **refactor-cleaner**: Dead code cleanup and refactoring
- **doc-updater**: Documentation updates and maintenance
- **e2e-runner**: End-to-end testing guidance

### Build & Troubleshooting
- **build-error-resolver**: General build error diagnosis and fixes
- **go-build-resolver**: Go-specific build error resolution

## Usage

When you select this template, all agents will be copied to your `.prompts/agents/` directory.

Each agent is independent and can be used based on your current task:
- Complex feature → Use **planner**
- Code written → Use **code-reviewer**
- Bug fix → Use **tdd-guide**
- Architecture → Use **architect**
- Security concern → Use **security-reviewer**

## Integration

All agents work together as a cohesive system. They follow consistent patterns and can be chained for complex workflows.
