from __PKG__.__MODULE__ import ExponentialFilter
import pytest


def test_first_sample_is_taken_as_is():
    assert ExponentialFilter(0.5).update(4.0) == 4.0


def test_moves_part_way_to_new_sample():
    f = ExponentialFilter(0.25)
    f.update(0.0)
    assert f.update(4.0) == pytest.approx(1.0)
