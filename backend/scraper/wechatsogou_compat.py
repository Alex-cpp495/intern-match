"""
wechatsogou 依赖已移除的 werkzeug.contrib.cache；用 cachelib 在导入前注入同名模块。
须在 import wechatsogou 之前调用 install_wechatsogou_werkzeug_shim()。
"""

from __future__ import annotations

import sys
from types import ModuleType


def install_wechatsogou_werkzeug_shim() -> None:
    if "werkzeug.contrib.cache" in sys.modules:
        return
    try:
        from cachelib import FileSystemCache
    except ImportError as e:
        raise ImportError(
            "使用 wechatsogou 请先安装: pip install cachelib wechatsogou",
        ) from e

    contrib = ModuleType("werkzeug.contrib")
    contrib.__path__ = []  # type: ignore[attr-defined]
    cache_mod = ModuleType("werkzeug.contrib.cache")
    cache_mod.FileSystemCache = FileSystemCache

    sys.modules["werkzeug.contrib"] = contrib
    sys.modules["werkzeug.contrib.cache"] = cache_mod
