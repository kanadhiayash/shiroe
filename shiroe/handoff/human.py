"""Human handoff wrapper."""

from shiroe.handoff.compiler import compile_handoff


def build(root=".", objective="Continue from current Zeref memory state.", include_private=False):
    return compile_handoff(root, target="human", objective=objective, include_private=include_private)
