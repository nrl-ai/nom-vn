# Releasing `nom-vn` to PyPI

The release flow is **GitHub Actions + PyPI Trusted Publishing** —
no API tokens stored in repo secrets, no `twine upload` from a laptop.

## One-time setup (already done; documented for posterity)

1. PyPI account → **Account settings → Publishing**.
2. Add a "trusted publisher" for `nom-vn`:
   - **Owner**: `nrl-ai` (the GitHub org / user that owns this repo)
   - **Repository name**: `nom-vn`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Same flow on `test.pypi.org` with environment `testpypi` for dry-runs.

After that, the workflow at `.github/workflows/publish.yml` can publish
without any token in the repo.

## Cutting a release — the canonical flow

Two equivalent paths. Pick whichever fits the moment.

### Path A — `gh release create`

```bash
# Bump version in pyproject.toml (e.g. 0.2.21 → 0.2.22)
# Add CHANGELOG.md entry
# Commit, push to main

gh release create v0.2.22 \
  --title "v0.2.22" \
  --notes-from-tag \
  --target main
```

This creates the tag, the GitHub release, and triggers the
`publish.yml` workflow on tag push.

### Path B — plain git tag

```bash
git tag v0.2.22
git push origin v0.2.22
```

Same effect. The workflow fires on `push: tags: ['v*.*.*']`.

### Path C — manual dry-run via TestPyPI

Before a real release, run the workflow manually pointed at TestPyPI:

```bash
gh workflow run publish.yml -f target=testpypi
```

Verify the upload:

```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps nom-vn
```

If the smoke install passes, do path A or B for real.

## What the workflow does

```
push tag v*.*.*
   │
   ├── validate-version   (read pyproject.toml, assert tag == "v" + version)
   │
   ├── test-before-publish (pytest, OCR stage deselected — runner has no Tesseract)
   │
   ├── build-ui  (pnpm install + pnpm build → src/nom/chat/ui_dist/)
   │
   ├── build  (python -m build → dist/*.whl + dist/*.tar.gz; assert wheel
   │           contains the UI bundle — fails the release if it doesn't)
   │
   └── publish-pypi  (Trusted Publishing OIDC → pypi.org)
```

Total runtime: ~3-5 minutes on a healthy GitHub runner.

## Sanity-check the wheel locally before tagging

```bash
# Same recipe the GH workflow uses, just locally
scripts/build_ui.sh
python -m build --sdist --wheel --outdir dist/

# Confirm the wheel ships the React UI:
python -c "
import glob, zipfile
whl = glob.glob('dist/*.whl')[0]
with zipfile.ZipFile(whl) as z:
    assert any('chat/ui_dist/index.html' in n for n in z.namelist()), 'UI bundle missing'
print(f'OK: {whl}')
"

# Install + smoke
pip install dist/nom_vn-*.whl
nom serve --in-memory  # → http://localhost:8080 should boot
```

If these all pass, the GH workflow will pass too — it does the same
checks plus the publish step.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Workflow fails at `validate-version` | tag != pyproject version | Either retag to match, or bump pyproject + push a new tag |
| `build` step says "UI bundle missing from .whl" | `pnpm build` didn't stage `ui_dist/` | Re-run `build-ui` job; check pnpm install used `--frozen-lockfile` against current `pnpm-lock.yaml` |
| `publish-pypi` says "no permission" | Trusted Publisher misconfigured | Re-check workflow filename + environment name on PyPI publishing page |
| Publish succeeds but `pip install nom-vn` shows old version | PyPI cache lag (~5-10 min) | Wait, retry. Don't republish — `skip-existing: false` will reject a same-version retry. Bump and re-tag. |
| Tag pushed but workflow didn't trigger | Tag pushed via amend / force-push | Push a new tag with a fresh name (PyPI doesn't allow re-uploading the same version anyway) |

## Why no `twine upload` here

PyPI Trusted Publishing is the [recommended path as of 2023+](https://docs.pypi.org/trusted-publishers/).

Pros:
- No API token to leak.
- OIDC tokens are short-lived (per-run) and bound to this exact workflow file.
- The "publishing identity" can be revoked in one click on PyPI without rotating tokens elsewhere.

Cons:
- One-time setup (the steps at the top of this doc). Worth it.
