"""Dataset loaders for the supported external benchmarks.

Each loader module exposes:

- ``NAME``, ``OFFICIAL_URL``, ``PINNED_VERSION``, ``PINNED_SHA256``
- ``DATA_FILENAME`` — the file expected inside the local dataset directory
- ``DOWNLOAD_INSTRUCTIONS`` — the manual download step (no auto-downloads)
- ``load(data_dir) -> list[Task]`` — parse into the common Task schema
- ``check(data_dir) -> DatasetCheck`` — offline validation with clear errors

Run any loader with ``python3 -m benchmarks.external.loaders.<name> --check DIR``.
"""

from __future__ import annotations

from benchmarks.external.loaders import convomem, helmet, locomo, longmemeval, personamem, ruler

LOADERS = {
    locomo.NAME: locomo,
    longmemeval.NAME: longmemeval,
    convomem.NAME: convomem,
    personamem.NAME: personamem,
    ruler.NAME: ruler,
    helmet.NAME: helmet,
}


def get_loader(name: str):
    try:
        return LOADERS[name]
    except KeyError:
        raise KeyError(
            f"unknown benchmark {name!r}; supported: {sorted(LOADERS)}. "
            "Unsupported benchmarks are listed with reasons in "
            "benchmarks/external/UNSUPPORTED.md"
        ) from None
