from __future__ import annotations

import contextlib
import sys
from typing import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.validation import ValidationError, Validator
from rich.console import Console

# ── palette ──────────────────────────────────────────────────────────────────
_PIPE   = "color(102)"   # #6c757d dim gray
_ACTIVE = "bold #7c3aed" # purple
_DONE   = "color(102)"   # dim gray
_VALUE  = "color(145)"   # #9ca3af light gray
_OK     = "bold #22c55e" # green
_ERR    = "bold #ef4444" # red
_WARN   = "#f59e0b"

_CLACK_STYLE = PTStyle.from_dict({
    "qmark":       "fg:#7c3aed bold",
    "question":    "bold",
    "answer":      "fg:#9ca3af",
    "pointer":     "fg:#7c3aed bold",
    "highlighted": "fg:#7c3aed bold",
    "selected":    "fg:#9ca3af",
    "separator":   "fg:#6c757d",
    "instruction": "fg:#6c757d",
    "text":        "",
})


class ClackUI:
    def __init__(self) -> None:
        # Pin to the real terminal stdout captured at startup — never follows sys.stdout = buf redirects
        self._stdout = sys.__stdout__ or sys.stdout
        self._console = Console(highlight=False, markup=True, file=self._stdout)

    # ── layout helpers ────────────────────────────────────────────────────────

    def _p(self, text: str = "") -> None:
        self._console.print(text)

    def _pipe_line(self) -> None:
        self._console.print(f"[{_PIPE}]│[/]")

    # ── public API ────────────────────────────────────────────────────────────

    def intro(self, title: str) -> None:
        self._stdout.write("\033[2J\033[H")
        self._stdout.flush()
        self._p(f"[{_PIPE}]┌[/]  {title}")
        self._pipe_line()

    def outro(self, msg: str) -> None:
        self._pipe_line()
        self._p(f"[{_PIPE}]└[/]  {msg}")

    def note(self, msg: str) -> None:
        self._console.print(f"[{_PIPE}]│[/]  {msg}")

    def step(self, msg: str, value: str | None = None) -> None:
        self._pipe_line()
        self._console.print(f"[{_DONE}]◇[/]  {msg}")
        if value is not None:
            self._console.print(f"[{_PIPE}]│[/]  [{_VALUE}]{value}[/]")
        self._pipe_line()

    def error(self, msg: str) -> None:
        self._console.print(f"[{_PIPE}]│[/]  [{_ERR}]✗[/] {msg}")

    def warn(self, msg: str) -> None:
        self._console.print(f"[{_PIPE}]│[/]  [{_WARN}]![/] {msg}")

    def text(
        self,
        question: str,
        *,
        password: bool = False,
        placeholder: str = "",
        validate: Callable[[str], str | None] | None = None,
        silent: bool = False,
    ) -> str:
        validator = None
        if validate:
            class _V(Validator):
                def validate(self_v, doc):
                    err = validate(doc.text)
                    if err:
                        raise ValidationError(message=err)
            validator = _V()

        # Fresh session per call — avoids validator bleed from previous prompts
        session = PromptSession(validator=validator, validate_while_typing=False)

        ph = HTML(f"<ansigray>{placeholder}</ansigray>") if placeholder else None

        # Print active block (2 lines — spacer + question header)
        self._stdout.write(f"\033[2m│\033[0m\n\033[1m\033[38;2;124;58;237m◆\033[0m  {question}\n")
        self._stdout.flush()

        answer = session.prompt(
            HTML('<ansibrightblack>│</ansibrightblack>  <ansigray>›</ansigray> '),
            is_password=password,
            placeholder=ph,
        )

        # Erase: our │ (1) + ◆ question (1) + prompt line (1) = 3 lines up
        self._stdout.write("\033[3A\033[J")
        self._stdout.flush()

        if not silent:
            display = "••••••••" if password else answer
            self._console.print(f"[{_PIPE}]│[/]")
            self._console.print(f"[{_DONE}]◇[/]  {question}")
            self._console.print(f"[{_PIPE}]│[/]  [{_VALUE}]{display}[/]")
            self._console.print(f"[{_PIPE}]│[/]")

        return answer

    def select(self, question: str, choices: list[str], *, silent: bool = False) -> str:
        import questionary

        # Print spacer before questionary takes over
        self._stdout.write(f"\033[2m│\033[0m\n")
        self._stdout.flush()

        result = questionary.select(
            question,
            choices=choices,
            qmark="◆",
            pointer="●",
            style=_CLACK_STYLE,
            use_jk_keys=False,
            use_shortcuts=False,
            instruction="",
        ).ask()

        if result is None:
            raise SystemExit("Cancelled.")

        # Erase: spacer(1) + questionary header(1) + N choices(len) = N+2 lines
        n = len(choices)
        self._stdout.write(f"\033[{n + 2}A\033[J")
        self._stdout.flush()

        if not silent:
            self._console.print(f"[{_PIPE}]│[/]")
            self._console.print(f"[{_DONE}]◇[/]  {question}")
            self._console.print(f"[{_PIPE}]│[/]  [{_VALUE}]{result}[/]")
            self._console.print(f"[{_PIPE}]│[/]")

        return result

    @contextlib.contextmanager
    def spin(self, msg: str):
        self.note(f"◌  {msg}")
        try:
            yield lambda _: None
        finally:
            pass
