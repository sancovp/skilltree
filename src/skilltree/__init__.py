"""SkillTree — a tree of skill dirs wired by links, with programmatic validation.

The substrate won't auto-traverse it (no nested-.claude auto-load), so the
validator is the system. Nodes are skill dirs of any type (ac/cor/sc/skill);
edges are symlinks; descending a level = redirecting the active skills root.
"""
from __future__ import annotations

# single source of truth = the installed dist (pyproject); can't drift from a literal again
from importlib.metadata import PackageNotFoundError, version as _pkg_version
try:
    __version__ = _pkg_version("agent-skilltree")
except PackageNotFoundError:        # running from a source checkout that isn't pip-installed
    __version__ = "0.2.2"

from .exchange import Exchange, Member, load_exchange
from .exchange import build as build_exchange
from .exchange import is_valid as exchange_is_valid
from .exchange import validate as validate_exchange
from .materialize import materialize
from .model import SkillTree, TreeNode, assign_coords, compose_summary, skill_name, assign_coords, skill_name
from .registry import (
    Entry,
    load_registry,
    promote,
    validate_contribution,
    validate_registry,
)
from .registry import search as registry_search
from .forest import build_forest, link_tree, list_links, unlink
from .reports import (
    list_reports,
    mark_problem,
    report_missed,
    resolve,
    summary as reports_summary,
)
from .search import build_index, search, search_tree, search_folder, DEFAULT_EXTS
from .mapper import build_map, write_map
from .cohere import (
    Finding, cohere, discover, emit, unemit,
    render_notifications, write_notifications, watch, NOTIFY_RULE,
)
from .federation import (
    flatten_federation,
    local_resolver,
    register_child,
    validate_federation,
    walk_federation,
)
from .validate import Violation, is_valid, validate

__all__ = [
    "SkillTree", "TreeNode", "materialize", "validate", "is_valid", "Violation",
    "Exchange", "Member", "load_exchange", "build_exchange", "validate_exchange",
    "exchange_is_valid",
    "Entry", "load_registry", "validate_registry", "validate_contribution",
    "promote", "registry_search",
    "walk_federation", "flatten_federation", "validate_federation",
    "register_child", "local_resolver",
    "link_tree", "build_forest", "list_links", "unlink",
    "assign_coords", "skill_name",
    "build_index", "search", "search_tree", "search_folder", "DEFAULT_EXTS",
    "build_map", "write_map",
    "discover", "cohere", "emit", "unemit", "Finding",
    "render_notifications", "write_notifications", "watch", "NOTIFY_RULE",
    "report_missed", "mark_problem", "list_reports", "resolve", "reports_summary",
    "__version__",
]
