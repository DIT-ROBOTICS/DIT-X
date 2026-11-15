"""Pure logic of __PKG__, kept free of ROS so it can be unit-tested directly.

Put the algorithm here; the node only moves data in and out.
"""


class ExponentialFilter:
    """First-order low-pass filter: y += alpha * (x - y). alpha in (0, 1], 1 = no smoothing."""

    def __init__(self, alpha):
        self.alpha = alpha
        self.value = None

    def update(self, x):
        self.value = x if self.value is None else self.value + self.alpha * (x - self.value)
        return self.value
