"""User modules — a small plugin system.

Drop a Python file in  <data>/modules/  that defines a top-level
``register(api)`` function.  The host calls it once at startup with a
``ModuleAPI``; from there a module can read or edit the data store, use the
backend's calculations and theme, and add its own page to the sidebar.

    # data/modules/hello.py
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    def register(api):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(api.helpers["label"](
            f"{len(api.store.items())} items tracked", api.theme.TEXT, 18, bold=True))
        lay.addStretch(1)
        api.add_page("hello", "Hello", w)        # optional: icon="goals"

A page widget may define ``set_context(self, doc, year, month)`` — it's called
whenever the data changes or the page is opened, so it can refresh.

SECURITY: modules are ordinary Python and run with the app's full privileges —
there is NO sandbox.  Only add module files you wrote or trust.
"""

from __future__ import annotations

import importlib.util
import os
import traceback

import datamanagement as dm


def modules_dir() -> str:
    """The folder scanned for user modules (created if missing)."""
    d = os.path.join(dm.DATA_DIR, "modules")
    os.makedirs(d, exist_ok=True)
    return d


class ModuleAPI:
    """The stable surface handed to each module's ``register(api)``.

    Internals of the app may change between versions; this object is the
    contract that modules are written against.
    """

    def __init__(self, store, backend, theme, helpers, navigate=None):
        self.store = store        # ItemStore — items(), transactions(), accounts(), people() + edit ops
        self.backend = backend    # backend module — occurrence engine, totals, net_worth, forecast, search…
        self.theme = theme        # theme module — colours & sizes (TEXT, GREEN, RADIUS, FONT_FAMILY…)
        self.helpers = helpers    # dict of UI builders: card, label, money, tile_row, scrollable, ProgressBar, LineChart…
        self._navigate = navigate  # optional: api.go("overview") to switch pages
        self.pages = []           # collected page specs

    def add_page(self, key: str, title: str, widget, icon: str = "module") -> None:
        """Register a sidebar page.  ``widget`` is a QWidget; if it has a
        ``set_context(doc, year, month)`` method it's refreshed on data change."""
        self.pages.append({"key": str(key), "title": str(title),
                           "widget": widget, "icon": icon})

    def go(self, page_key: str) -> None:
        """Navigate to a page (built-in key, or 'mod:<your key>')."""
        if self._navigate:
            self._navigate(page_key)


def load_modules(api: ModuleAPI):
    """Import every  <data>/modules/*.py  and call its ``register(api)``.
    Returns (loaded_filenames, errors) where errors is [(filename, traceback)].
    A failing module never crashes the host — its error is collected instead."""
    loaded, errors = [], []
    d = modules_dir()
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(d, fname)
        try:
            spec = importlib.util.spec_from_file_location(f"usermod_{fname[:-3]}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "register"):
                errors.append((fname, "no register(api) function found"))
                continue
            mod.register(api)
            loaded.append(fname)
        except Exception:
            errors.append((fname, traceback.format_exc()))
    return loaded, errors
