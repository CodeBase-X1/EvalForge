# Publishing EvalForge to PyPI

## One-time setup (do this once)

### 1. Create PyPI accounts

- **PyPI**: https://pypi.org/account/register/
- **TestPyPI**: https://test.pypi.org/account/register/

### 2. Enable Trusted Publishing (no API keys needed)

This is the modern way — GitHub Actions publishes directly without storing secrets.

**On PyPI:**
1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in:
   - PyPI project name: `evalforge`
   - GitHub owner: `your-username`
   - Repository name: `evalforge`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

**On TestPyPI** (same steps at https://test.pypi.org/manage/account/publishing/):
   - Environment name: `testpypi`

### 3. Create GitHub Environments

In your GitHub repo → Settings → Environments:

- Create environment named `pypi`
- Create environment named `testpypi`
- (Optional) Add required reviewers to `pypi` for extra safety

---

## Releasing a new version

```bash
# 1. Bump the version
python scripts/bump_version.py patch   # or minor / major

# 2. Update CHANGELOG.md — move items from [Unreleased] to the new version section

# 3. Commit and tag
git add pyproject.toml evalforge/__init__.py CHANGELOG.md
git commit -m "chore: bump version to v0.1.1"
git tag v0.1.1
git push && git push --tags
```

That's it. GitHub Actions will:
1. Run CI (tests + lint) on all Python versions
2. Build the wheel and sdist
3. Run `twine check` to validate
4. Publish to TestPyPI
5. Publish to PyPI
6. Create a GitHub Release with the changelog

---

## Manual publish (if needed)

```bash
# Build
python -m build

# Check
twine check dist/*

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test the install
pip install --index-url https://test.pypi.org/simple/ evalforge

# Upload to PyPI
twine upload dist/*
```

---

## Verifying the release

```bash
pip install evalforge==0.1.1
evalforge --version
# evalforge 0.1.1
```

---

## Install extras

Users can install optional feature sets:

```bash
pip install evalforge              # core only (CLI + clustering + exporters)
pip install evalforge[ui]          # + web dashboard
pip install evalforge[agent]       # + Google ADK agent
pip install evalforge[phoenix]     # + Arize Phoenix client
pip install evalforge[embeddings]  # + sentence-transformers (local embeddings)
pip install evalforge[all]         # everything
```
