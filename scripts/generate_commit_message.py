# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/19 22:43
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :
"""
import fnmatch
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict

import click
import dotenv
from google import genai
from google.genai import types
from loguru import logger
from pydantic import BaseModel, Field

dotenv.load_dotenv()

SYSTEM_INSTRUCTIONS = """
You are an expert programmer tasked with writing a high-quality Git commit message.
Your goal is to generate a message that follows the Conventional Commits specification.
The message must be clear, concise, and provide enough context for other developers.

## Commit Message Format

```xml
<type>(<scope>): <title>

<body>

<footer>
```

**1. Title:**

   - Format: `<type>(<scope>): <title>`
   - `type`: Must be one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
   - `scope` (optional): The part of the codebase affected (e.g., `api`, `ui`, `db`).
   - `title`: A short summary of the change, in imperative mood (e.g., "add", "fix", "change" not "added", "fixed", "changed"). No period at the end.

**2. Body (optional):**
   - Provides more context, explaining the "what" and "why" of the change.
   - Use bullet points for lists.

**3. Footer (optional):**
   - For referencing issues (e.g., `Closes: #123`) or breaking changes (`BREAKING CHANGE:`).

## Few-shot Examples

[Example 1: A new feature]

- **Changes:** Added `POST /users` endpoint.
- **Good Commit:**
  ```json
  {
    "type": "feat",
    "scope": "api",
    "title": "add user creation endpoint",
    "body": "This commit introduces a new endpoint `POST /users` to allow for the creation of new users. It includes input validation and basic error handling.",
    "footer": "Closes: #42"
  }
  ```
  

[Example 1 End]

[Example 2: A bug fix]
- **Changes:** Corrected a calculation error in the payment module.
- **Good Commit:**
  ```json
  {
    "type": "fix",
    "scope": "payment",
    "title": "correct off-by-one error in tax calculation",
    "body": "The tax calculation was using a wrong index, leading to an off-by-one error. This has been corrected by adjusting the loop boundary.",
    "footer": ""
  }
  ```
  

[Example 2 End]

[Example 3: Refactoring with no functional change]

- **Changes:** Replaced a legacy class with a new, more efficient one.
- **Good Commit:**
  ```json
  {
    "type": "refactor",
    "scope": "core",
    "title": "replace LegacyManager with NewService",
    "body": "Refactored the core module to use the `NewService` class instead of the deprecated `LegacyManager`. This improves performance and readability without changing external behavior.",
    "footer": ""
  }
  ```

[Example 3 End]

---

Now, based on the provided git changes, generate a commit message in the specified JSON format.
"""

USER_PROMPT_TEMPLATE = """
Generate a git commit message for the following changes.

## Git Branch Name:
{branch_name}

## Staged Changes (git diff --staged):
```diff
{diff_content}
```

## Your Task:
Provide the commit message as a single JSON object, following the rules and format specified in the system instructions. Do not add any text before or after the JSON object.
"""

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Maximum context length (number of characters), 40k
MAX_CONTEXT_LENGTH = 40960

# Special document handling rules
SPECIAL_FILE_HANDLERS = {
    ".ipynb": "Summarized notebook changes.",
    "package-lock.json": "Updated dependencies.",
    "pnpm-lock.yaml": "Updated dependencies.",
    "yarn.lock": "Updated dependencies.",
    "poetry.lock": "Updated dependencies.",
}


class LLMInput(BaseModel):
    """Model for data passed to the LLM generation module."""

    git_branch_name: str = Field(...)
    diff_content: str = Field(..., description="Formatted and potentially compressed git diff.")
    full_diff_for_reference: str | None = Field(
        default=None, description="The full, uncompressed diff."
    )


class CommitMessage(BaseModel):
    """Structured output for the generated commit message."""

    type: str = Field(..., description="Commit type (e.g., 'feat', 'fix').")
    scope: str | None = Field(default=None, description="Optional scope of the changes.")
    title: str = Field(..., description="Short, imperative-mood title.")
    body: str | None = Field(default=None, description="Detailed explanation of the changes.")
    footer: str | None = Field(default=None, description="Footer for issues or breaking changes.")

    def to_git_message(self) -> str:
        """Formats the object into a git-commit-ready string."""
        header = f"{self.type}"
        if self.scope:
            header += f"({self.scope})"
        header += f": {self.title}"

        message_parts = [header]
        if self.body:
            message_parts.append(f"\n{self.body}")
        if self.footer:
            message_parts.append(f"\n{self.footer}")

        return "\n".join(message_parts)


class GitCommitGenerator:
    """A class to generate git commit messages."""

    def __init__(self, max_context: int = MAX_CONTEXT_LENGTH, auto_push: bool = False):
        """
        Initializes the generator. Automatically finds the git repository root.
        """
        self.repo_path = self._find_git_root()
        self.max_context = max_context
        self.auto_push = auto_push

        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._model = MODEL_NAME

        logger.debug(f"GitCommitGenerator initialized for repository: {self.repo_path}")

    def count_tokens(self, text: str) -> int:
        response = self._client.models.count_tokens(model=self._model, contents=text)
        return response.total_tokens

    @staticmethod
    def _find_git_root() -> Path:
        """
        Finds the root directory of the git repository using `git rev-parse --show-toplevel`.
        This allows the script to be run from any subdirectory of the repository.
        """
        try:
            # It's a standard, reliable way to find the root directory of a warehouse #
            git_root_str = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.PIPE
            ).strip()
            return Path(git_root_str)
        except subprocess.CalledProcessError:
            # If this command fails, neither the current directory nor its parent is a Git repository
            logger.error("Fatal: Not a git repository (or any of the parent directories).")
            raise ValueError("This script must be run from within a Git repository.")

    @staticmethod
    def _is_ignored(file_path: str, ignore_patterns: List[str]) -> bool:
        """Check if a file path matches any ignore pattern."""
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def _call_llm_api(self, llm_input: LLMInput) -> CommitMessage | None:
        """
        调用 Dify Workflow 中的快捷指令，跳过意图识别触发特性分支。
        Args:
            llm_input:

        Returns:

        """
        logger.debug("Invoke commit_message_generation tool.")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            branch_name=llm_input.git_branch_name, diff_content=llm_input.diff_content
        )

        config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=CommitMessage,
            thinking_config=types.ThinkingConfig(include_thoughts=False, thinking_budget=0),
        )

        response = self._client.models.generate_content(
            model=self._model, contents=user_prompt, config=config
        )
        return CommitMessage(**response.parsed.model_dump())

    def _run_command(self, command: List[str], input_: Optional[str] = None) -> str:
        """
        Runs a command, optionally passing stdin, and returns its stdout.

        Args:
            command: The command to run as a list of strings.
            input_: Optional string to be passed as standard input to the command.

        Returns:
            The stdout of the command as a string.
        """
        try:
            # All git commands will be executed under the correct repo_path
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf8",
                input=input_,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command '{' '.join(command)}' failed with error:\n{e.stderr}")
            raise

    def _get_ignore_patterns(self) -> List[str]:
        """Reads .gitignore and .dockerignore and returns a list of patterns."""
        patterns = []
        for ignore_file in [".gitignore", ".dockerignore"]:
            path = self.repo_path / ignore_file
            if path.exists():
                logger.debug(f"Reading ignore patterns from '{path}'")
                with open(path, "r", encoding="utf8") as f:
                    patterns.extend(
                        line.strip() for line in f if line.strip() and not line.startswith("#")
                    )
        return patterns

    def _collect_changes(self) -> str:
        """
        Collects unstaged changes from the working directory by running `git diff`.
        This mirrors the "Changes" view in GitHub Desktop.
        """
        logger.debug("Collecting unstaged changes from the working directory (using 'git diff')...")

        # Key change: use 'git diff' to scan workspace instead of 'git diff --staged'
        diff_output = self._run_command(["git", "diff"])

        if not diff_output:
            logger.warning("No unstaged changes found in the working directory.")
            return ""

        ignore_patterns = self._get_ignore_patterns()

        # Split diff output by file (this parsing logic also works for 'git diff')
        file_diffs = re.split(r'diff --git a/.* b/(.*)', diff_output)

        filtered_diffs = []
        if len(file_diffs) > 1:
            for i in range(1, len(file_diffs), 2):
                file_path = file_diffs[i].strip()
                diff_content = file_diffs[i + 1]

                if self._is_ignored(file_path, ignore_patterns):
                    logger.debug(f"Ignoring file specified in ignore list: {file_path}")
                    continue

                header = f"diff --git a/{file_path} b/{file_path}"
                filtered_diffs.append(header + diff_content)

        if not filtered_diffs:
            logger.warning("All changes were on ignored files. No changes to commit.")
            return ""

        logger.success(
            f"Collected diffs for {len(filtered_diffs)} files from the working directory."
        )
        return "\n".join(filtered_diffs)

    def _compress_context(self, diff_content: str) -> str:
        """Compresses the diff content if it exceeds the max length."""
        len_diff_content = self.count_tokens(diff_content)
        if len_diff_content <= self.max_context:
            return diff_content

        logger.warning(
            f"Diff content ({len_diff_content} tokens) exceeds max context length ({self.max_context}). Compressing..."
        )

        file_diffs = re.split(r'(diff --git .*)', diff_content)
        if file_diffs[0] == '':
            file_diffs = file_diffs[1:]

        total_len = 0

        # First, process special files and small files
        file_summaries: List[Dict] = []
        for i in range(0, len(file_diffs), 2):
            header = file_diffs[i]
            content = file_diffs[i + 1]
            match = re.search(r'b/(.*)', header)
            if not match:
                continue

            file_path = match.group(1).strip()

            file_summaries.append(
                {
                    "path": file_path,
                    "header": header,
                    "content": content,
                    "len": len(header) + len(content),
                    "is_special": any(file_path.endswith(ext) for ext in SPECIAL_FILE_HANDLERS),
                }
            )

        # Sort: special files first, then by length (smallest first)
        file_summaries.sort(key=lambda x: (not x['is_special'], x['len']))

        final_diff_parts = []
        files_summarized = []

        for summary in file_summaries:
            file_path = summary['path']

            # Special file handling (e.g., .ipynb, lock files)
            for ext, message in SPECIAL_FILE_HANDLERS.items():
                if file_path.endswith(ext):
                    summary_line = f"--- Summary for {file_path} ---\n{message}\n"
                    len_summary_line = self.count_tokens(summary_line)
                    if total_len + len_summary_line <= self.max_context:
                        final_diff_parts.append(summary_line)
                        total_len += len_summary_line
                    else:
                        files_summarized.append(
                            f"- {file_path} (special file, not included due to size)"
                        )
                    break
            else:  # Not a special file
                diff_part = summary['header'] + summary['content']
                len_diff_part = self.count_tokens(diff_part)
                if total_len + len_diff_part <= self.max_context:
                    final_diff_parts.append(diff_part)
                    total_len += len_diff_part
                else:
                    files_summarized.append(f"- {file_path} (content truncated due to size)")

        if files_summarized:
            summary_header = (
                "\n--- The following files had large diffs and were summarized or omitted ---\n"
            )
            final_diff_parts.append(summary_header + "\n".join(files_summarized))

        compressed_output = "".join(final_diff_parts)
        logger.success(
            f"Compressed diff from {len(diff_content)} to {len(compressed_output)} chars."
        )
        return compressed_output

    def _generate_prompt_data(self) -> LLMInput | None:
        """Generates the input data for the LLM."""
        branch_name = self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        full_diff = self._collect_changes()

        if not full_diff:
            return

        compressed_diff = self._compress_context(full_diff)

        return LLMInput(
            git_branch_name=branch_name,
            diff_content=compressed_diff,
            full_diff_for_reference=full_diff,
        )

    def _apply_commit(self, commit_message: CommitMessage):
        """
        Stages all changes from the working directory and then applies the commit.
        This ensures the committed files match what the LLM analyzed.
        """
        message_str = commit_message.to_git_message()
        logger.debug(f"Applying git commit with message:\n---\n{message_str}\n---")

        try:
            if self.auto_push:
                # Stage all workspace changes before committing (equivalent to GitHub Desktop)
                logger.debug("Staging all changes from the working directory ('git add .')...")
                self._run_command(["git", "add", "."])

                # Use -F - Read multi-line messages from standard input for commit
                self._run_command(["git", "commit", "-F", "-"], input_=message_str)
                logger.success("Commit applied successfully!")

                # Push if auto-push is enabled
                self._push_changes()

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply commit. Git output:\n{e.stdout}\n{e.stderr}")

    def _push_changes(self):
        """Push the committed changes to the remote repository."""
        try:
            logger.debug("Pushing changes to remote repository...")
            # Get current branch name
            current_branch = self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

            # Push to origin with the current branch
            self._run_command(["git", "push", "origin", current_branch])
            logger.success(f"Successfully pushed changes to origin/{current_branch}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push changes. Git output:\n{e.stdout}\n{e.stderr}")
            raise

    def run(self):
        """Main execution flow."""
        try:
            # 1. Generate prompt data (includes collecting and compressing changes)
            if not (llm_input := self._generate_prompt_data()):
                logger.warning("No changes to commit. Exiting.")
                return

            # 2. Call LLM to get a structured commit message
            if not (commit_message_obj := self._call_llm_api(llm_input)):
                logger.error("Failed to generate commit message.")
                return

            # 3. Apply the commit
            self._apply_commit(commit_message_obj)

        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")


@click.command()
@click.option(
    '--push',
    is_flag=True,
    default=False,
    help='Automatically push changes to remote repository after successful commit.',
)
def main(push: bool):
    """Generate a git commit message and apply commit with optional auto-push."""
    # Check if you are in a git repository
    if not Path(".git").is_dir():
        logger.error("This script must be run from the root of a Git repository.")
    else:
        generator = GitCommitGenerator(auto_push=push)
        generator.run()


if __name__ == "__main__":
    main()
