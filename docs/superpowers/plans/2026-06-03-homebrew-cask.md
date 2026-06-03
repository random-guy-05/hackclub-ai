# Homebrew Cask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible Homebrew cask release path for HackClub AI that installs the DMG, removes quarantine, and launches the app automatically.

**Architecture:** Store the app version in one file, generate the Homebrew cask from a Python script, and keep the generated cask checked into the repo. The cask targets the GitHub Release DMG and runs the approved post-install commands.

**Tech Stack:** Python 3 stdlib, Homebrew cask DSL, existing shell build script

---

### Task 1: Lock the cask contract with tests

**Files:**
- Create: `tests/test_homebrew_cask.py`
- Test: `tests/test_homebrew_cask.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.generate_homebrew_cask import render_cask

def test_rendered_cask_contains_release_url_and_postflight():
    cask = render_cask("1.2.3", "abc123")
    assert 'version "1.2.3"' in cask
    assert 'releases/download/v#{version}/HackClub-AI.dmg' in cask
    assert 'xattr' in cask
    assert 'open' in cask
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_homebrew_cask.py -v`
Expected: FAIL with module import or missing symbol error

- [ ] **Step 3: Write minimal implementation**

```python
def render_cask(version, sha256):
    return f'version "{version}" sha256 "{sha256}"'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_homebrew_cask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_homebrew_cask.py
git commit -m "test: lock homebrew cask output"
```

### Task 2: Implement generator and generated cask

**Files:**
- Create: `scripts/generate_homebrew_cask.py`
- Create: `Casks/hackclub-ai.rb`
- Create: `VERSION`
- Modify: `scripts/build_macos_app.sh`
- Test: `tests/test_homebrew_cask.py`

- [ ] **Step 1: Write the failing test for version loading or output path**

```python
def test_read_version_trims_whitespace():
    self.assertEqual(read_version_text("1.2.3\n"), "1.2.3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_homebrew_cask.py -v`
Expected: FAIL with missing helper

- [ ] **Step 3: Write minimal implementation**

```python
def read_version_text(text):
    return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_homebrew_cask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add VERSION scripts/generate_homebrew_cask.py Casks/hackclub-ai.rb scripts/build_macos_app.sh tests/test_homebrew_cask.py
git commit -m "feat: add homebrew cask generation"
```

### Task 3: Document install and release flow

**Files:**
- Modify: `README.md`
- Test: `python3 -m unittest tests/test_homebrew_cask.py -v`

- [ ] **Step 1: Write the failing doc expectation by identifying the missing install method**

```text
README does not yet describe Homebrew install or cask publishing.
```

- [ ] **Step 2: Update README with the new install method and release workflow**

```markdown
### Method 1 — Install with Homebrew

brew install --cask https://raw.githubusercontent.com/random-guy-05/hackclub-ai/main/Casks/hackclub-ai.rb
```

- [ ] **Step 3: Verify docs and tests**

Run: `python3 -m unittest tests/test_homebrew_cask.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add homebrew install flow"
```
