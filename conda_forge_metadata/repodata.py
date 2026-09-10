"""Utilities to deal with repodata"""

from __future__ import annotations

import bz2
import json
import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from itertools import product
from logging import getLogger
from pathlib import Path
from typing import Any, Literal
from urllib.request import urlretrieve

import requests

logger = getLogger(__name__)

SUBDIRS = (
    "linux-64",
    "linux-aarch64",
    "linux-ppc64le",
    "linux-riscv64",
    "osx-64",
    "osx-arm64",
    "win-64",
    "win-arm64",
    "noarch",
)
CACHE_DIR = Path(".repodata_cache")


@lru_cache
def all_labels(use_remote_cache: bool = False) -> list[str]:
    if use_remote_cache:
        r = requests.get(
            "https://raw.githubusercontent.com/conda-forge/"
            "by-the-numbers/main/data/labels.json"
        )
        r.raise_for_status()
        return r.json()

    if token := os.environ.get("BINSTAR_TOKEN"):
        label_info = requests.get(
            "https://api.anaconda.org/channels/conda-forge",
            headers={"Authorization": f"token {token}"},
        ).json()

        return sorted(label for label in label_info if "/" not in label)

    logger.warning("Could not fetch all labels; returning 'main' only as a fallback")
    return ["main"]


def fetch_repodata(
    subdirs: Iterable[str] = SUBDIRS,
    force_download: bool = False,
    cache_dir: str | Path = CACHE_DIR,
    label: str = "main",
) -> list[Path]:
    assert all(subdir in SUBDIRS for subdir in subdirs)
    paths = []
    for subdir in subdirs:
        if label == "main":
            repodata = f"https://conda.anaconda.org/conda-forge/{subdir}/repodata.json"
        else:
            repodata = (
                "https://conda.anaconda.org/conda-forge/"
                f"label/{label}/{subdir}/repodata.json"
            )
        local_fn = Path(cache_dir, f"{subdir}.{label}.json")
        local_fn_bz2 = Path(str(local_fn) + ".bz2")
        paths.append(local_fn)
        if force_download or not local_fn.exists():
            logger.info("Downloading %s to %s", repodata, local_fn)
            local_fn.parent.mkdir(parents=True, exist_ok=True)
            # Download the file
            urlretrieve(f"{repodata}.bz2", local_fn_bz2)
            with open(local_fn_bz2, "rb") as compressed, open(local_fn, "wb") as f:
                f.write(bz2.decompress(compressed.read()))
            local_fn_bz2.unlink()
    return paths


def _iter_repodatas(
    repodata_jsons: Iterable[str | Path],
    include_broken: bool = True,
) -> Iterable[tuple[str, str, str, dict[str, object]]]:
    """
    Repodata JSON filenames MUST be `{subdir}.{label}.json`.

    Yields label, subdir, filename, record tuples.

    Note: When include_broken is True, some records may be empty.
    """
    for repodata in sorted(repodata_jsons):
        repodata = Path(repodata)
        subdir, label, *_ = repodata.stem.split(".")
        assert subdir in SUBDIRS, (
            "Invalid repodata file name. Must be '<subdir>.<label>.json'."
        )
        data = json.loads(repodata.read_text())
        keys = ["packages", "packages.conda"]
        if include_broken:
            keys.append("removed")
        for key in keys:
            if key == "removed":
                for fn in data.get(key, ()):
                    yield label, subdir, fn, {}
            else:
                for fn, record in data.get(key, {}).items():
                    yield label, subdir, fn, record


def list_artifacts(
    repodata_jsons: Iterable[str | Path],
    include_broken: bool = True,
) -> Iterable[str]:
    for _, subdir, fn, _ in _iter_repodatas(
        repodata_jsons=repodata_jsons, include_broken=include_broken
    ):
        yield f"{subdir}/{fn}"


def repodata(subdir: str) -> dict[str, Any]:
    assert subdir in SUBDIRS
    path = fetch_repodata(subdirs=(subdir,))[0]
    return json.loads(path.read_text())


def aggregated(
    reports: Iterable[Literal["artifacts", "names", "size"]],
    labels: Iterable[str] = ("main",),
    include_broken: bool = True,
) -> dict[str, int]:
    with_artifacts = "artifacts" in reports
    with_names = "names" in reports
    with_size = "size" in reports
    seen_artifacts, seen_names, size = set(), set(), 0
    futures = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for label, subdir in product(labels, SUBDIRS):
            future = executor.submit(fetch_repodata, (subdir,), False, CACHE_DIR, label)
            futures.append(future)
        for future in as_completed(futures):
            repodatas = future.result()
            for label, subdir, fn, record in _iter_repodatas(
                repodatas, include_broken=include_broken
            ):
                if with_artifacts:
                    seen_artifacts.add(
                        f"{label}/{subdir}/{fn}/{record.get('sha256') or record.get('md5') or ''}"
                    )
                if with_names:
                    seen_names.add(record.get("name") or fn.rsplit("-", 2)[0])
                if with_size:
                    size += record.get("size") or 0  # type: ignore

    result: dict[str, int] = {}
    if with_artifacts:
        result["artifacts"] = len(seen_artifacts)
    if with_names:
        result["names"] = len(seen_names)
    if with_size:
        result["size"] = size

    return result
