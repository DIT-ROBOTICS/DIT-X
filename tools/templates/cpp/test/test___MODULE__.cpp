#include <gtest/gtest.h>

#include "__PKG__/__MODULE__.hpp"

TEST(ExponentialFilter, FirstSampleIsTakenAsIs) {
  __PKG__::ExponentialFilter f(0.5);
  EXPECT_DOUBLE_EQ(f.update(4.0), 4.0);
}

TEST(ExponentialFilter, MovesPartWayToNewSample) {
  __PKG__::ExponentialFilter f(0.25);
  f.update(0.0);
  EXPECT_DOUBLE_EQ(f.update(4.0), 1.0);
}
