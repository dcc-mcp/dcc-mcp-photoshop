"""Execute arbitrary JavaScript/UXP code in Adobe Photoshop."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def execute_script(code: str, **kwargs) -> dict:
    """Execute JavaScript/UXP code in Photoshop.

    Use this for advanced operations not covered by typed tools.
    The code runs in Photoshop's UXP scripting environment.

    Args:
        code: JavaScript/UXP code string to execute.

    Returns:
        dict: ActionResultModel with the script execution result.
    """
    app = Photoshop()

    return action_result(
        "Executed JavaScript in Photoshop",
        lambda: _run_script(app, code),
        prompt="The script has been executed. Check the result for details.",
    )


def _run_script(app: Photoshop, code: str) -> dict:
    result = app.eval_js(code)
    return {"result": result}


def main(**kwargs) -> dict:
    return execute_script(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
