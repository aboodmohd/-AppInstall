"""Opt-in PyO3 pilot; not imported by AppInstall."""

from . import _native
from ._native import categories_for, category_for, filtered_rows


def featured_rows(rows, source, query="", limit=6):
    return _native.featured_rows(rows, source, query, limit)

__all__ = ["categories_for", "category_for", "featured_rows", "filtered_rows"]
