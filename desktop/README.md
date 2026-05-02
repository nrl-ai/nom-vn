# Desktop app — packaging and dev

The desktop shell wraps the existing FastAPI app (`nom serve`) in a
native window via [pywebview](https://pywebview.flowrl.com/). Packaged
to a single distributable directory by PyInstaller.

Architecture:

```
┌─ pywebview window (Python main thread) ──────────────┐
│  • Native menus (OS-provided WKWebView/WebView2/      │
│    WebKitGTK)                                         │
│  • F12 dev tools when --debug                         │
└──┬───────────────────────────────────────────────────┘
   │ same process, daemon thread
   ▼
┌─ uvicorn (background thread) ─────┐
│ FastAPI app from nom.chat.server  │
│ on http://127.0.0.1:<free port>   │
└──────────────────────────────────┘
```

Ollama runs as a separate user-managed service for now; bundling Ollama
as a sidecar binary lands in v0.5 (see "Roadmap" below).

## Prerequisites

- Python 3.10+ with the project's dev environment.
- `pip install -e ".[chat,desktop]"` to pull pywebview + PyInstaller +
  the FastAPI runtime.
- Per-OS native webview backend:
  - **Linux:** `apt install libwebkit2gtk-4.1-dev` (Debian/Ubuntu) or
    equivalent. pywebview also needs `gir1.2-webkit2-4.1`.
  - **macOS:** WKWebView ships with the OS — no install needed.
  - **Windows:** WebView2 Runtime is on every Windows 11 machine and
    most Windows 10 machines after 2022. The PyInstaller bundle does
    not currently chain-install it; document the dep in the v1
    installer.
- The React UI bundle must be built before packaging:
  ```bash
  scripts/build_ui.sh        # populates src/nom/chat/ui_dist/
  ```
  The PyInstaller spec force-includes `ui_dist/`; without it the
  shipped binary won't render the chat UI.

## Dev — fast iteration

```bash
# Run unfrozen with hot reload of the React UI side
cd ui && pnpm dev &     # proxies /api → :8090
python -m nom.desktop --debug --port 8090
```

`--debug` opens pywebview's developer tools (F12 / right-click → Inspect)
and turns up uvicorn log verbosity. Use this whenever you're iterating
on the embedded server or the UI.

## Build (per-OS, run from repo root)

```bash
# 1. Make sure the UI bundle is fresh
scripts/build_ui.sh

# 2. Run PyInstaller against the spec
pyinstaller desktop/nom-app.spec --clean --noconfirm

# 3. Smoke-test the bundle
./dist/nom-app/nom-app
```

Output: `dist/nom-app/` — a folder with the bundled binary + all
runtime files. Distribute the whole folder, or wrap it in:

- **Linux:** `appimagetool` for an `.AppImage`, or `fpm` for a `.deb`.
- **macOS:** `pyinstaller --osx-bundle-identifier ...` plus `dmgbuild`
  for a `.dmg`. Notarization through `xcrun notarytool` is required
  for distribution outside the dev machine.
- **Windows:** `wix` or `nsis` for a `.msi` / `.exe` installer. EV
  code-signing cert needed to avoid SmartScreen warnings.

These wrap-it-up steps are tracked in v0.8 of the roadmap; v0.0 ships
the raw `dist/nom-app/` folder.

## Icons

Place platform icons under `desktop/icons/`:

- `nom.ico` — Windows
- `nom.icns` — macOS
- `nom.png` — Linux (any size; the spec doesn't currently use it)

The spec auto-detects `.ico` and `.icns` and bakes whichever is
available. Skip if you're just running locally — pywebview falls back
to a default icon.

## Known issues

- **Cold start ~3-5s** on first launch as the FastAPI app initializes
  Vietnamese embeddings (sentence-transformers download on first run).
  v0.5 first-run wizard will move this into a visible progress step
  instead of leaving the user staring at a blank window.
- **Ollama not bundled.** Currently the user must install + start
  Ollama separately for the chat backend to work. The status page on
  the home tab surfaces this. Bundling lands in v0.5.
- **Linux WebKitGTK quirks**: GPU acceleration is sometimes broken
  under Wayland; falling back to X11 (`GDK_BACKEND=x11`) usually fixes
  flicker.

## Roadmap

| Phase | Adds |
|---|---|
| v0.0 (this commit) | Tauri-equivalent shell — pywebview window over the embedded server, PyInstaller bundle, build instructions |
| v0.5 | First-run wizard with hardware probe + 3-tier model recommendation; bundled Ollama as a sidecar binary; download UX with progress, pause/resume, disk-space check |
| v0.8 | Auto-update channel (signed releases via a self-hosted manifest); per-OS installers (`.dmg` / `.msi` / `.AppImage`); code-signing keys wired into release CI |
| v1.0 | Distribution channel (download page on the marketing site, telemetry opt-in, crash reports), tray-resident mode |
