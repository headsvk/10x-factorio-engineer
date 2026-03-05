# Skill Structure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the repo so `skill/` is a self-contained distributable unit and development tooling lives in `dev/`.

**Architecture:** Move `cli.py` + data JSON files into `skill/assets/` so the skill folder is complete on its own. Move `test_cli.py` and `generate_preview.py` into a new `dev/` folder that is never shipped. Fix the one path reference inside `cli.py` and the import in `test_cli.py`.

**Tech Stack:** Python stdlib, unittest, file moves via shell.

---

### Task 1: Create `dev/` and move `test_cli.py` into it with a working import path

`test_cli.py` currently does `import cli` which works because both files are at the root.
After `cli.py` moves to `skill/assets/`, that import will break unless we fix it.

**Files:**
- Create: `dev/test_cli.py` (moved + patched from `test_cli.py`)
- Delete: `test_cli.py`

**Step 1: Verify current tests pass before touching anything**

```bash
python -m unittest test_cli -v
```
Expected: 59 tests, all pass.

**Step 2: Create `dev/test_cli.py` — copy and add the path fix at the top**

Open `test_cli.py`, read the full contents, then write `dev/test_cli.py` with these two lines inserted immediately before `import cli`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skill', 'assets'))
```

The rest of the file is identical to the original.

**Step 3: Verify the new file fails to import (cli.py not moved yet)**

```bash
python -m unittest dev.test_cli -v
```
Expected: `ModuleNotFoundError: No module named 'cli'` — confirms the path fix is wired correctly and will work once cli.py lands in `skill/assets/`.

**Step 4: Delete the old `test_cli.py` from root**

```bash
rm test_cli.py
```

---

### Task 2: Move `cli.py` to `skill/assets/` and fix its `DATA_DIR`

`cli.py` line 60 currently reads:
```python
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
```
After the move, data files will be in the same directory as `cli.py` (`skill/assets/`), so `"data"` becomes `"."` — or more cleanly, just `os.path.dirname(os.path.abspath(__file__))`.

**Files:**
- Create: `skill/assets/cli.py` (moved + patched from `cli.py`)
- Delete: `cli.py`

**Step 1: Copy `cli.py` to `skill/assets/cli.py`**

```bash
cp cli.py skill/assets/cli.py
```

**Step 2: Update `DATA_DIR` in `skill/assets/cli.py`**

Change line 60 from:
```python
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
```
to:
```python
DATA_DIR   = os.path.dirname(os.path.abspath(__file__))
```

**Step 3: Run the dev tests — they should now pass**

```bash
python -m unittest dev.test_cli -v
```
Expected: 59 tests, all pass.

**Step 4: Delete the old `cli.py` from root**

```bash
rm cli.py
```

**Step 5: Verify tests still pass with the root file gone**

```bash
python -m unittest dev.test_cli -v
```
Expected: 59 tests, all pass.

---

### Task 3: Move data JSON files to `skill/assets/`

**Files:**
- Move: `data/vanilla-2.0.55.json` → `skill/assets/vanilla-2.0.55.json`
- Move: `data/space-age-2.0.55.json` → `skill/assets/space-age-2.0.55.json`
- Delete: `data/` directory

**Step 1: Move the files**

```bash
mv data/vanilla-2.0.55.json skill/assets/vanilla-2.0.55.json
mv data/space-age-2.0.55.json skill/assets/space-age-2.0.55.json
rmdir data
```

**Step 2: Run tests to confirm data loading works from the new location**

```bash
python -m unittest dev.test_cli -v
```
Expected: 59 tests, all pass.

**Step 3: Commit**

```bash
git add skill/assets/cli.py skill/assets/vanilla-2.0.55.json skill/assets/space-age-2.0.55.json dev/test_cli.py
git add -u   # stage deletions of cli.py, test_cli.py, data/
git commit -m "$(cat <<'EOF'
refactor: make skill/ self-contained, move dev tooling to dev/

cli.py and data JSON files now live in skill/assets/ so the skill folder
is a complete distributable unit. test_cli.py moves to dev/ with a
sys.path fix to import cli from its new location.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Move `generate_preview.py` to `dev/` and update its paths

`generate_preview.py` is currently in `skill/scripts/`. It needs to move to `dev/` and its path constants need updating:
- `SKILL_DIR` should point to `skill/` (one level up from `dev/`, then into `skill/`)
- `JSX_PATH` reads from `skill/assets/dashboard.jsx` (unchanged relative location)
- `OUT_PATH` writes `preview.html` into `dev/` (alongside the script itself)

**Files:**
- Create: `dev/generate_preview.py` (moved + patched from `skill/scripts/generate_preview.py`)
- Delete: `skill/scripts/generate_preview.py`
- Delete: `skill/scripts/` directory

**Step 1: Write `dev/generate_preview.py`**

Copy `skill/scripts/generate_preview.py`, then change the path constants block (currently lines 15–18) to:

```python
REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR  = os.path.join(REPO_ROOT, "skill")
JSX_PATH   = os.path.join(SKILL_DIR, "assets", "dashboard.jsx")
OUT_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview.html")
```

**Step 2: Run the script to verify it works**

```bash
python dev/generate_preview.py
```
Expected output:
```
Written: dev/preview.html
  JSX source:  skill/assets/dashboard.jsx  (NNN lines)
  Output size: NNN bytes
...
```

**Step 3: Delete the old location and empty directory**

```bash
rm skill/scripts/generate_preview.py
rmdir skill/scripts
```

**Step 4: Add `dev/preview.html` to `.gitignore`**

Open `.gitignore` and append:
```
dev/preview.html
```

**Step 5: Commit**

```bash
git add dev/generate_preview.py dev/preview.html .gitignore
git add -u   # stage deletion of skill/scripts/generate_preview.py
git commit -m "$(cat <<'EOF'
refactor: move generate_preview.py to dev/, output preview.html there too

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Update `SKILL.md` references

Every place SKILL.md says `python cli.py` needs to become `python skill/assets/cli.py`. The Section 6 preview command also needs updating.

**Files:**
- Modify: `skill/SKILL.md`

**Step 1: Update all CLI invocation examples in Section 2**

Find every occurrence of `python cli.py` and replace with `python skill/assets/cli.py`.

There are approximately 6 occurrences in Section 2 (the examples block and the step-by-step protocol).

**Step 2: Update the preview command in Section 6**

Change:
```
python skill/scripts/generate_preview.py
```
to:
```
python dev/generate_preview.py
```

**Step 3: Verify no stale references remain**

```bash
grep -n "cli\.py\|generate_preview\|skill/scripts\|data/" skill/SKILL.md
```
Expected: only `skill/assets/cli.py` and `dev/generate_preview.py` appear. No bare `cli.py`, no `skill/scripts`, no `data/`.

---

### Task 6: Update `CLAUDE.md`

**Files:**
- Modify: `claude.md`

**Step 1: Update the Repository Layout table**

Replace:
```
| `cli.py` | Calculator — entire implementation, stdlib only |
| `test_cli.py` | `unittest` suite (59 tests, stdlib only) |
| `data/vanilla-2.0.55.json` | KirkMcDonald dataset — base game |
| `data/space-age-2.0.55.json` | KirkMcDonald dataset — Space Age DLC |
```
with:
```
| `skill/assets/cli.py` | Calculator — entire implementation, stdlib only |
| `skill/assets/vanilla-2.0.55.json` | KirkMcDonald dataset — base game |
| `skill/assets/space-age-2.0.55.json` | KirkMcDonald dataset — Space Age DLC |
| `dev/test_cli.py` | `unittest` suite (59 tests, stdlib only) — dev only |
| `dev/generate_preview.py` | Script that builds `dev/preview.html` for local dev |
```

Also remove the row for `skill/scripts/generate_preview.py` (now gone).

**Step 2: Update the CLI docstring path note**

In the Component 1 section, the docstring excerpt refers to `./data/`. Update to reflect that data files live alongside `cli.py` in `skill/assets/`.

**Step 3: Update the test run command**

Find the test invocation:
```bash
python -m unittest test_cli -v
```
Change to:
```bash
python -m unittest dev.test_cli -v
```

**Step 4: Verify no stale paths remain**

```bash
grep -n "test_cli\b\|data/\|generate_preview\|skill/scripts" claude.md
```
Expected: only `dev/test_cli`, `skill/assets/`, `dev/generate_preview.py`.

**Step 5: Commit**

```bash
git add skill/SKILL.md claude.md
git commit -m "$(cat <<'EOF'
docs: update SKILL.md and CLAUDE.md for new skill/ structure

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Final verification

**Step 1: Confirm skill/ folder contains exactly the right files**

```bash
find skill/ -type f | sort
```
Expected:
```
skill/SKILL.md
skill/assets/cli.py
skill/assets/dashboard.jsx
skill/assets/space-age-2.0.55.json
skill/assets/vanilla-2.0.55.json
skill/references/strategy-topics.md
```

**Step 2: Confirm dev/ folder**

```bash
find dev/ -type f | sort
```
Expected:
```
dev/generate_preview.py
dev/preview.html   (or absent if not yet run)
dev/test_cli.py
```

**Step 3: Confirm data/ and root cli.py are gone**

```bash
ls cli.py test_cli.py data/ 2>&1
```
Expected: "No such file or directory" for all three.

**Step 4: Full test run**

```bash
python -m unittest dev.test_cli -v
```
Expected: 59 tests, all pass.

**Step 5: Smoke-test the CLI directly**

```bash
python skill/assets/cli.py --item electronic-circuit --rate 60
```
Expected: valid JSON with `iron-ore` and `copper-ore` in `raw_resources`.
