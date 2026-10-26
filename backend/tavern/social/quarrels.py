"""How hot a quarrel has run, read from the insults a scene's last turns hold."""

from collections.abc import Mapping
from typing import Any


def heat(scene: Mapping[str, Any]) -> int:
    """Count the insults two guests have traded, one after the other, at the end of a scene.

    Args:
        scene: A conversation scene with its `turns`.

    Returns:
        The length of the run of `insult` turns ending the scene, each addressed to the guest who spoke the one
        before it. Any other act, a third speaker, one speaker twice in a row, or an insult to nobody in
        particular ends the run; 0 for a scene with no turns or whose last turn is not an insult.
    """
    run, later = 0, None
    for turn in reversed(scene["turns"]):
        if turn["act"] != "insult" or turn["addressee"] is None:
            break
        # Each insult answers the one after it: the later speaker is the one this turn insulted, and the reverse.
        if later is not None and (later["speaker"] != turn["addressee"] or later["addressee"] != turn["speaker"]):
            break
        run, later = run + 1, turn
    return run
