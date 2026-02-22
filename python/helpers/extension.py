from abc import abstractmethod
from typing import Any
from python.helpers import extract_tools, files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent import Agent


DEFAULT_EXTENSIONS_FOLDER = "python/extensions"
USER_EXTENSIONS_FOLDER = "usr/extensions"

_cache: dict[str, list[type["Extension"]]] = {}
_guard_cache: list | None = None


class Extension:

    def __init__(self, agent: "Agent|None", **kwargs):
        self.agent: "Agent" = agent  # type: ignore < here we ignore the type check as there are currently no extensions without an agent
        self.kwargs = kwargs

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass


def _get_guard_handlers() -> list:
    global _guard_cache
    if _guard_cache is not None:
        return _guard_cache
    from importlib.metadata import entry_points

    eps = entry_points(group="agent_zero.guards")
    _guard_cache = []
    for ep in eps:
        try:
            _guard_cache.append(ep.load())
        except Exception:
            from python.helpers.print_style import PrintStyle
            PrintStyle.warning(f"Failed to load guard entry_point: {ep.name}")
    return _guard_cache


async def call_extensions(
    extension_point: str, agent: "Agent|None" = None, **kwargs
) -> Any:
    from python.helpers import projects, subagents

    # build mutable event dict from kwargs
    event: dict[str, Any] = dict(**kwargs)
    event.setdefault("extension_point", extension_point)
    event.setdefault("agent", agent)

    # search for extension folders in all agent's paths
    paths = subagents.get_paths(agent, "extensions", extension_point, default_root="python")
    all_exts = [cls for path in paths for cls in _get_extensions(path)]

    # merge: first ocurrence of file name is the override
    unique = {}
    for cls in all_exts:
        file = _get_file_from_module(cls.__module__)
        if file not in unique:
            unique[file] = cls
    classes = sorted(
        unique.values(), key=lambda cls: _get_file_from_module(cls.__module__)
    )

    # execute unique file-based extensions (no fault isolation — preserve existing behavior)
    for cls in classes:
        await cls(agent=agent).execute(_event=event, **kwargs)

    # execute entry_point guard handlers (with fault isolation per handler)
    for handler in _get_guard_handlers():
        try:
            await handler(event, agent=agent)
        except Exception:
            from python.helpers.print_style import PrintStyle
            PrintStyle.error(f"Guard handler {handler!r} failed for '{extension_point}'")

    return event


def _get_file_from_module(module_name: str) -> str:
    return module_name.split(".")[-1]


def _get_extensions(folder: str):
    global _cache
    folder = files.get_abs_path(folder)
    if folder in _cache:
        classes = _cache[folder]
    else:
        if not files.exists(folder):
            return []
        classes = extract_tools.load_classes_from_folder(folder, "*", Extension)
        _cache[folder] = classes

    return classes
