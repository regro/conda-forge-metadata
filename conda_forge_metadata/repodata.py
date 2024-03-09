"""
Utilities to deal with repodata
"""

import bz2
import json
from logging import getLogger
from pathlib import Path
from typing import Iterable, List, Generator, Union, Dict, Any
from urllib.request import urlretrieve

logger = getLogger(__name__)

SUBDIRS = (
    "linux-64",
    "osx-64",
    "win-64",
    "linux-aarch64",
    "linux-ppc64le",
    "osx-arm64",
)
CACHE_DIR = Path("repodata_cache")


def fetch_repodata(
    subdirs: Iterable[str] = SUBDIRS,
    force_download: bool = False,
    cache_dir: Union[str, Path] = CACHE_DIR,
) -> List[Path]:
    assert all(subdir in SUBDIRS for subdir in subdirs)
    paths = []
    for subdir in subdirs:
        repodata = f"https://conda.anaconda.org/conda-forge/{subdir}/repodata.json"
        local_fn = Path(cache_dir, f"{subdir}.json")
        local_fn_bz2 = Path(cache_dir, f"{subdir}.json.bz2")
        paths.append(local_fn)
        if force_download or not local_fn.exists():
            logger.info(f"Downloading {repodata} to {local_fn}")
            local_fn.parent.mkdir(parents=True, exist_ok=True)
            # Download the file
            urlretrieve(f"{repodata}.bz2", local_fn_bz2)
            with open(local_fn_bz2, "rb") as compressed, open(local_fn, "wb") as f:
                f.write(bz2.decompress(compressed.read()))
            local_fn_bz2.unlink()
    return paths


def list_artifacts(
    repodata_jsons: Iterable[Union[str, Path]],
    include_broken: bool = True,
) -> Generator[str, None, None]:
    for repodata in sorted(repodata_jsons):
        repodata = Path(repodata)
        subdir = repodata.stem
        data = json.loads(repodata.read_text())
        keys = ["packages", "packages.conda"]
        if include_broken:
            keys.append("removed")
        for key in keys:
            for pkg in data[key]:
                yield f"{subdir}/{pkg}"


def repodata(subdir: str) -> Dict[str, Any]:
    assert subdir in SUBDIRS
    path = fetch_repodata(subdirs=(subdir,))[0]
    return json.loads(path.read_text())


def n_artifacts() -> int:
    repodatas = fetch_repodata()
    count = 0
    for _ in list_artifacts(repodatas):
        count += 1
    return count
