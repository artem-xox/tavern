"""Voice files: each guest's stock lines, read from a directory and checked at the boundary."""

import json
from pathlib import Path

from tavern.mind.phrasebook import Phrasebook, check_phrasebook

_FIELDS = {"card_hash", "lines"}


def load_voices(directory: Path) -> dict[str, Phrasebook]:
    """Read every voice file in a directory.

    Args:
        directory: Holds `<character id>.json` files of `card_hash` (what the card said when the lines were
            written, see `scripts/voices.py`) and `lines` (a phrasebook, see `phrasebook.check_phrasebook`).

    Returns:
        The phrasebook of each character, by the ID in the file's name. Other files are not voices.

    Raises:
        ValueError: The directory is missing, or a voice file is not JSON of exactly those fields, with a
            nonempty hash and a valid phrasebook. The message names the file.
    """
    if not directory.is_dir():
        raise ValueError(f"The voices directory {directory} is missing")
    voices: dict[str, Phrasebook] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or set(data) != _FIELDS:
                raise ValueError(f"a voice file holds exactly {sorted(_FIELDS)}")
            if not isinstance(data["card_hash"], str) or not data["card_hash"]:
                raise ValueError("card_hash must be nonempty text")
            voices[path.stem] = check_phrasebook(data["lines"])
        except ValueError as error:  # JSON errors are ValueErrors too.
            raise ValueError(f"Invalid voice file {path.name} (for {path.stem}): {error}") from error
    return voices
