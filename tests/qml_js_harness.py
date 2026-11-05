"""Test the actual QML JavaScript adapters in Node without a Plasma shell.

Qt recognizes .pragma/.import lines that Node doesn't. The generated harness
models the same namespace imports and explicitly exports the public methods.
This does not emulate QML signals or Wayland pointer delivery.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "plasmoid/contents/ui/adapters"


def _body(filename: str) -> str:
    source = (ADAPTERS / filename).read_text()
    return "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith((".pragma ", ".import ")))


def bundle_adapter_js() -> str:
    result = []
    for var, filename, functions in [
        ("Plasma", "PlasmaLauncher.js", ["closeExpanded", "originalIsOpen",
             "originalIsVisiblyOpen", "closeOriginal", "activate", "describeState", "chooseIcon"]),
        ("AppGrid", "AppGridLauncher.js", ["matches", "hasLegacyWindow", "originalIsOpen",
             "originalIsVisiblyOpen", "hideOwnedAppGridWindow", "closeOriginal",
             "supportsPanelPassThrough", "describeState", "requestStandaloneHide", "trace"]),
        ("LauncherAdapters", "LauncherAdapters.js", ["kind", "closeOriginal", "originalIsOpen",
             "originalIsVisiblyOpen", "activate", "chooseIcon", "describeState",
             "trace", "traceDismissal", "traceRequest", "deferSignalClose", "requestAsyncClose"]),
    ]:
        result.append(f"var {var} = (function () {{\n{_body(filename)}\n"
                      f"return {{{', '.join(f+' : '+f for f in functions)}}};\n}})();")
    # Existing JS tests can continue calling the public contract as globals,
    # while integration tests exercise the dispatcher namespace directly.
    for name in ("closeOriginal", "originalIsOpen", "originalIsVisiblyOpen",
                 "activate", "chooseIcon", "describeState", "trace", "traceDismissal", "traceRequest", "deferSignalClose", "requestAsyncClose"):
        result.append(f"function {name}(...args) {{ return LauncherAdapters.{name}(...args); }}")
    result.append("function requestStandaloneHide(...args) { return AppGrid.requestStandaloneHide(...args); }")
    result.append("function closeExpanded(item) { return Plasma.closeExpanded(item); }")
    result.append("function hideOwnedAppGridWindow(item) { return AppGrid.hideOwnedAppGridWindow(item); }")
    result.append("function hasLegacyWindow(item) { return AppGrid.hasLegacyWindow(item); }")
    return "\n".join(result)
