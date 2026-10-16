"""Self-check for placing the old maps: uv run python -m pipeline.test_s14"""
import numpy as np

from .s03_tiles import ORIGIN
from .s14_oldmaps import MAPS, fit, tile_box

# an affine map is fitted exactly, at either order, and in the direction asked: ground to image
pts = [[x, y, 25496000 + 2 * x - 0.1 * y, 6674000 - 0.1 * x - 2 * y]
       for x, y in [(0, 0), (100, 0), (0, 100), (100, 100), (50, 20), (30, 80), (70, 40)]]
for order in (1, 2):
    to_image, res = fit(pts, order)
    assert res.max() < 1e-6, order
    assert np.allclose(to_image(np.array([[25496000 + 200 - 10, 6674000 - 10 - 200]])), [[100, 100]])
# the quadtree is web/app.js's: the root centred on Senaatintori, and level 8's tiles 256 m from there
w, n, s = tile_box(0, 0, 0)
assert np.allclose((w + s / 2, n - s / 2), ORIGIN)
assert np.allclose(tile_box(8, 128, 128), (ORIGIN[0], ORIGIN[1], 256))
# each map's fit holds its control points to a few pixels
for id, m in MAPS.items():
    _, res = fit(m["points"], m["order"])
    assert np.median(res) < 5, (id, np.median(res))
print("ok")
