import ast
import os
import traceback
from typing import Optional


async def meval(code: str, globs: dict, **kwargs):
    globs = globs.copy()

    global_key = "_globs"
    while global_key in globs:
        global_key = "_" + global_key

    kwargs[global_key] = {
        key: globs[key]
        for key in ("__name__", "__package__")
        if key in globs
    }

    root = ast.parse(code, mode="exec")
    if not root.body:
        return None

    return_name = "_ret"
    while (
        any(
            isinstance(node, ast.Name) and node.id == return_name
            for node in ast.walk(root)
        )
        or return_name in globs
    ):
        return_name = "_" + return_name

    body = []
    body.append(
        ast.Expr(
            ast.Call(
                func=ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id="globals", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    attr="update",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[
                    ast.keyword(arg=None, value=ast.Name(id=global_key, ctx=ast.Load()))
                ],
            )
        )
    )
    body.append(
        ast.Assign(
            targets=[ast.Name(id=return_name, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )
    )

    for node in root.body:
        if isinstance(node, ast.Expr):
            new_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=return_name, ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[node.value],
                    keywords=[],
                )
            )
            ast.copy_location(new_node, node)
            body.append(new_node)
        else:
            body.append(node)

    body.append(ast.Return(value=ast.Name(id=return_name, ctx=ast.Load())))

    function = ast.AsyncFunctionDef(
        name="tmp",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[ast.arg(arg=key) for key in kwargs.keys()],
            kw_defaults=[None] * len(kwargs),
            kwarg=None,
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )
    ast.fix_missing_locations(function)

    local_vars = {}
    exec(
        compile(ast.Module([function], type_ignores=[]), "<meval>", "exec"),
        {},
        local_vars,
    )

    result = await local_vars["tmp"](**kwargs)
    if not result:
        return None

    result = [await value if hasattr(value, "__await__") else value for value in result]
    result = [value for value in result if value is not None]

    return result[0] if len(result) == 1 else (result or None)


def format_exception(
    exc: BaseException,
    tb: Optional[list[traceback.FrameSummary]] = None,
) -> str:
    if tb is None:
        tb = traceback.extract_tb(exc.__traceback__)

    cwd = os.getcwd()
    for frame in tb:
        if cwd in frame.filename:
            frame.filename = os.path.relpath(frame.filename)

    return (
        "Traceback (most recent call last):\n"
        f"{''.join(traceback.format_list(tb))}"
        f"{type(exc).__name__}{': ' + str(exc) if str(exc) else ''}"
  )
