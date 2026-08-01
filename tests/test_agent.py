from msclaw.agent import ALLOWED_TOOLS


def test_builtin_tool_names_match_sdk_conventions() -> None:
    assert {"Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Bash"} <= set(
        ALLOWED_TOOLS
    )
    assert not {"read", "write", "bash"} & set(ALLOWED_TOOLS)
