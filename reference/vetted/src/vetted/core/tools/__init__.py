"""Local operator tools.

These are not CLI commands. The Typer CLI in `vetted.core.cli` remains help-only with a single
`doctor` command, because `report_and_cli_score_display_scope` is still an unresolved policy
key. A module here is invoked directly with `python -m`, prints to the terminal, and writes
nothing.

Importing any module in this package must have no side effects: the test suite imports every
`careerops.*` module, so all execution lives under `if __name__ == "__main__":`.
"""
