"""Constants for ar-sync."""

# Default target directories/files to sync
# Add new IDE configurations here
DEFAULT_TARGETS: list[str] = [
    ".claude",                        # Claude Code
    ".clauderules",                   # Claude rules
    ".cursor",                        # Cursor IDE
    ".cursorrules",                   # Cursor rules
    ".windsurf",                      # Windsurf IDE
    ".windsurfrules",                 # Windsurf rules
    ".clinerules",                    # Cline rules
    ".kiro",                          # Kiro IDE
    ".gemini",                        # Gemini
    ".qwen",                          # Qwen
    ".serena",                        # Serena
    ".zed",                           # Zed editor
    ".vscode",                        # VS Code
    ".github/copilot-instructions.md",  # GitHub Copilot
    ".aider",                         # Aider
    ".aiderignore",                   # Aider ignore
    "AGENTS.md",                      # AI agent instructions
]

# Sync modes
SYNC_MODE_LINK = "link"
SYNC_MODE_COPY = "copy"
