"""s15_shore's step: each pixel turns from water to land once, where that disagrees least with the sources."""
import numpy as np

from .s15_shore import step

# Columns: water in the first two sources, then land; land throughout; never land; water in three, land in the last two.
obs = np.array([[0, -1, 1, 0], [0, -1, 1, 0], [-1, -1, 1, 0], [1, 1, 1, 1], [1, 1, 1, 1]], np.int8)
k, last = step(obs, np.ones(5))
assert list(k) == [3, 3, 0, 3], k            # an unread source before the first land does not make it earlier
assert list(last) == [1, -1, -1, 2], last    # the last source to show water before it
k, _ = step(np.array([[0], [0], [1], [0], [1], [1]], np.int8), np.ones(6))
assert k[0] == 4, k                          # a lone misreading (a ship, a pier) loses to the sources around it
k, _ = step(np.array([[0], [-1], [0]], np.int8), np.ones(3))
assert k[0] == 3, k                          # never land: not known
print("ok")
