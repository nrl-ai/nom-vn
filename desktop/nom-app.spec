# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build config for the Nôm desktop app.

Build: ``pyinstaller desktop/nom-app.spec --clean --noconfirm`` (run
from repo root). Output lands in ``dist/nom-app/``. See
``desktop/README.md`` for prerequisites and per-OS notes.
"""

from pathlib import Path

import PyInstaller.utils.hooks as hooks

# Anchor relative paths to the .spec location, not the cwd at build time.
SPEC_DIR = Path(SPECPATH)  # noqa: F821 — PyInstaller injects SPECPATH at exec
REPO = SPEC_DIR.parent
SRC = REPO / "src"
ENTRY = SRC / "nom" / "desktop" / "main.py"
UI_DIST = SRC / "nom" / "chat" / "ui_dist"
ICON = SPEC_DIR / "icons" / "nom"  # PyInstaller picks .ico/.icns by platform

# Pre-built React UI bundle. Required at runtime; the chat server
# refuses to start without it. Force-include even though it's gitignored.
datas = []
if UI_DIST.exists():
    for item in UI_DIST.rglob("*"):
        if item.is_file():
            datas.append((str(item), str(item.relative_to(SRC).parent)))

# FastAPI / Pydantic / sentence-transformers / transformers do dynamic
# imports that PyInstaller's static analyzer can miss. Be explicit.
hiddenimports = [
    # FastAPI runtime
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Nôm package — explicit so frozen builds don't drop submodules
    "nom",
    "nom.chat",
    "nom.chat.cli",
    "nom.chat.server",
    "nom.chat.store",
    "nom.chat.sqlite_store",
    "nom.chat.tools_api",
    "nom.llm",
    "nom.llm.ollama",
    "nom.embeddings",
    "nom.text",
    "nom.text.normalize",
    "nom.text.segment",
    "nom.doc",
    "nom.doc.pipeline",
    "nom.doc.stages",
    "nom.translate",
    "nom.translate.formats.docx",
]
# Pull every nom.* submodule discoverable on disk, in case we forget one.
hiddenimports += hooks.collect_submodules("nom")

# Bundle data files for libraries that ship runtime assets.
datas += hooks.collect_data_files("sentence_transformers", include_py_files=False)
datas += hooks.collect_data_files("transformers", include_py_files=False)


a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy libs we never call at runtime in the desktop bundle.
        "tkinter",
        "matplotlib",
        "pandas",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="nom-app",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX trips Windows SmartScreen and signed-app verification.
    console=False,  # GUI app — no terminal window on Windows / macOS.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.with_suffix(".ico").exists() or ICON.with_suffix(".icns").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="nom-app",
)
