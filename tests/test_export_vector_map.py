import numpy as np

from scripts.export_vector_map import project_to_3d


def test_project_to_3d_shape_and_range():
    rng = np.random.default_rng(0)
    emb = rng.normal(size=(200, 768))
    out = project_to_3d(emb)
    assert out.shape == (200, 3)
    assert out.min() >= -1.0001
    assert out.max() <= 1.0001


def test_project_to_3d_is_deterministic():
    rng = np.random.default_rng(1)
    emb = rng.normal(size=(50, 768))
    a = project_to_3d(emb)
    b = project_to_3d(emb)
    assert np.allclose(a, b)
