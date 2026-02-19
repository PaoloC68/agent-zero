from __future__ import annotations

import re, json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from python.helpers import files, print_style

if TYPE_CHECKING:
    from agent import Agent

# Extracts target selector from <meta name="plugin-target" content="...">
_META_TARGET_RE = re.compile(
    r'<meta\s+name=["\']plugin-target["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

META_FILE_NAME = "plugin.json"
SETTINGS_FILE_NAME = "settings.json"

@dataclass(slots=True)
class PluginListItem:
    name: str
    path: Path


def get_plugin_roots() -> List[str]:
    """Plugin root directories, ordered by priority (user first)."""
    # Project-specific plugins (commented out for now, will add project/agent plugins later)
    # projects = files.find_existing_paths_by_pattern("usr/projects/*/.a0proj/plugins")
    return [
        # *projects,
        files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR),
        files.get_abs_path(files.PLUGINS_DIR),
    ]


def list_plugins() -> List[PluginListItem]:
    """Discover plugins by directory convention. First root wins on ID conflict."""
    by_id: Dict[str, PluginListItem] = {}
    for root in get_plugin_roots():
        root_path = Path(root)
        if not root_path.exists():
            continue
        for d in sorted(root_path.iterdir(), key=lambda p: p.name):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if d.name not in by_id:
                by_id[d.name] = PluginListItem(name=d.name, path=d)
    return list(by_id.values())


def find_plugin_dir(plugin_name: str):
    """Find a single plugin by ID."""
    if not plugin_name:
        return None

    # check if the plugin is in the user directory
    user_plugin_path = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name, META_FILE_NAME)
    if files.exists(user_plugin_path):
        return files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name)
    
    # check if the plugin is in the default directory
    default_plugin_path = files.get_abs_path(files.PLUGINS_DIR, plugin_name, META_FILE_NAME)
    if files.exists(default_plugin_path):
        return files.get_abs_path(files.PLUGINS_DIR, plugin_name)
    
    return None


def get_plugin_paths(*subpaths: str) -> List[str]:
    """
    Resolve existing directories under each plugin matching subpaths.

    Example:
        get_plugin_paths("extensions", "python", "monologue_end")
        -> ["/abs/plugins/memory/extensions/python/monologue_end", ...]
    """
    sub = "/".join(subpaths) if subpaths else ""
    paths: List[str] = []
    for plugin in list_plugins():
        candidate = str(plugin.path / sub) if sub else str(plugin.path)
        if Path(candidate).is_dir() and candidate not in paths:
            paths.append(candidate)
    return paths


def get_webui_extensions(extension_point:str, filters:List[str]|None=None) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    effective_filters = filters or ["*"]
    for plugin in list_plugins():
        frontend_dir = plugin.path / "extensions" / "webui" / extension_point
        if not frontend_dir.is_dir():
            continue
        matched_files: List[Path] = []
        seen: set[str] = set()
        for pattern in effective_filters:
            for p in frontend_dir.rglob(pattern):
                if not p.is_file():
                    continue
                p_str = str(p)
                if p_str in seen:
                    continue
                seen.add(p_str)
                matched_files.append(p)

        for ext_file in sorted(matched_files, key=lambda p: p.name):
            try:
                rel_path = files.deabsolute_path(str(ext_file))
                entry: Dict[str, Any] = {
                    "plugin_name": plugin.name,
                    "path": rel_path,
                }
                entries.append(entry)
            except Exception:
                print_style.PrintStyle.error(f"Failed to load frontend extension file {ext_file}")
    return entries

def get_plugin_settings(plugin_name:str, agent:Agent|None):
    file_path = find_plugin_file(plugin_name, SETTINGS_FILE_NAME, agent=agent)
    if file_path:
        return json.loads(files.read_file(file_path))
    return None

def save_plugin_settings(plugin_name:str, project_name:str, agent_profile:str, settings:dict):
    file_path = determine_plugin_save_file_path(plugin_name, project_name, agent_profile, SETTINGS_FILE_NAME)
    if file_path:
        files.write_file(file_path, json.dumps(settings))

def find_plugin_file(plugin_name:str, *subpaths:str, agent:Agent|None=None):
    profile_name = agent.config.profile if agent and agent.config.profile else ""
    project_name = ""

    if agent:
        from python.helpers import projects
        project_name = projects.get_context_project_name(agent.context) or ""

        if project_name and profile_name:
            # project/.a0proj/agents/<profile>/plugins/<plugin_name>/...
            project_agent_file = projects.get_project_meta_folder(
                project_name, files.AGENTS_DIR, profile_name, files.PLUGINS_DIR, plugin_name, *subpaths
            )
            if files.exists(project_agent_file):
                return project_agent_file

        if project_name:
            # project/.a0proj/plugins/<plugin_name>/...
            project_file = projects.get_project_meta_folder(project_name, files.PLUGINS_DIR, plugin_name, *subpaths)
            if files.exists(project_file):
                return project_file

    if profile_name:
        from python.helpers import subagents
        # usr/agents/<profile>/plugins/<plugin_name>/...
        path = files.get_abs_path(subagents.USER_AGENTS_DIR, profile_name, files.PLUGINS_DIR, plugin_name, *subpaths)
        if files.exists(path):
            return path

        # agents/<profile>/plugins/<plugin_name>/...
        path = files.get_abs_path(subagents.DEFAULT_AGENTS_DIR, profile_name, files.PLUGINS_DIR, plugin_name, *subpaths)
        if files.exists(path):
            return path

    # usr/plugins/<plugin_name>/...
    path = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name, *subpaths)
    if files.exists(path):
        return path

    # plugins/<plugin_name>/...
    path = files.get_abs_path(files.PLUGINS_DIR, plugin_name, *subpaths)
    if files.exists(path):
        return path

    return None
    
def determine_plugin_save_file_path(plugin_name:str, project_name:str, agent_profile:str, *subpaths:str):
    base_path = files.get_abs_path(files.USER_DIR)
    
    if project_name:
        from python.helpers import projects
        base_path = projects.get_project_meta_folder(project_name)

    if agent_profile:
        base_path = files.get_abs_path(base_path, files.AGENTS_DIR, agent_profile)

    return files.get_abs_path(base_path, files.PLUGINS_DIR, plugin_name, *subpaths)