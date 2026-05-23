# fda-strategy-triples Makefile
# Requires: Python ≥ 3.10, make, git, huggingface-cli

PYTHON     := python
PIP        := pip
VERSION    := 0.1.0
RELEASE_DIR := data/releases/v$(VERSION)
HF_REPO    := datasets/hf_repo
HF_HUB_ID  := $(shell git config user.name | tr ' ' '-' | tr '[:upper:]' '[:lower:]')/fda-strategy-triples

.PHONY: help install release test lint publish-pypi publish-hf clean

help:
	@echo "Targets:"
	@echo "  install       pip install -e '.[dev]'"
	@echo "  release       Generate frozen release artefacts for v$(VERSION)"
	@echo "  test          Run pytest test suite"
	@echo "  lint          Run ruff + mypy"
	@echo "  publish-pypi  Build sdist/wheel and upload to PyPI"
	@echo "  publish-hf    Push datasets/hf_repo/ to Hugging Face Hub"
	@echo "  clean         Remove build artefacts"

install:
	$(PIP) install -e ".[dev]"

release:
	$(PYTHON) scripts/generate_release.py --version v$(VERSION)
	@echo "Release artefacts written to $(RELEASE_DIR)/ and src/fda_strategy_triples/releases/v$(VERSION)/"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/fda_strategy_triples/

publish-pypi: clean
	$(PYTHON) -m pip install --upgrade build twine
	$(PYTHON) -m build
	$(PYTHON) -m twine upload dist/*

publish-hf:
	@echo "Pushing $(HF_REPO)/ to Hugging Face Hub as dataset $(HF_HUB_ID)…"
	$(PYTHON) - <<'EOF'
import sys
try:
    from huggingface_hub import HfApi
except ImportError:
    print("huggingface_hub not installed. Run: pip install huggingface_hub")
    sys.exit(1)
import os, pathlib
repo_id = os.environ.get("HF_REPO_ID", "$(HF_HUB_ID)")
api = HfApi()
api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
api.upload_folder(
    folder_path="$(HF_REPO)",
    repo_id=repo_id,
    repo_type="dataset",
    commit_message="chore: release v$(VERSION)",
)
print(f"Pushed to https://huggingface.co/datasets/{repo_id}")
EOF

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info
