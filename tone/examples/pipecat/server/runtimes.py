"""Audience's and Tone's reference runtimes, side by side in one process, and their model files.

Each release ships its runtime as two packages, `contracts` and `harness`, with different modules
inside (Audience: `contracts.schemas.addressee`, `harness.addressee`; Tone:
`contracts.schemas.line_tags`, `harness.expression`). Both runtime folders go on the path, and each
package they share is told to look in both. Import this before either model's modules.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from loguru import logger

from config import AUDIENCE_DIR, TONE_DIR

ROOTS = [AUDIENCE_DIR / "runtime", TONE_DIR / "runtime"]
SHARED = ("contracts", "contracts.schemas", "harness")

for root in reversed(ROOTS):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
for package in SHARED:
    module = importlib.import_module(package)
    for root in ROOTS:
        path = str(root / package.replace(".", "/"))
        if path not in module.__path__:
            module.__path__.append(path)


def model_dir(release: Path, files: list[str], hf: tuple[str, str]) -> Path:
    """Where a model's files are: its release folder if it has them, else Hugging Face's cache,
    downloading them the first time."""
    if all((release / f).exists() for f in files):
        return release
    from huggingface_hub import snapshot_download

    repo, revision = hf
    logger.info(f"No model files in {release}; fetching {repo}@{revision}")
    return Path(snapshot_download(repo, revision=revision, allow_patterns=files))
