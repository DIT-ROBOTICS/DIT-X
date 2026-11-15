cmake_minimum_required(VERSION 3.16)
project(__PKG__)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(eurobot_common REQUIRED)
find_package(eurobot_interfaces REQUIRED)

add_executable(__NODE__ src/__NODE__.cpp)
target_include_directories(__NODE__ PRIVATE include)
target_link_libraries(__NODE__ eurobot_common::eurobot_common)
ament_target_dependencies(__NODE__ rclcpp eurobot_interfaces)

install(TARGETS __NODE__ DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test___MODULE__ test/test___MODULE__.cpp)
  target_include_directories(test___MODULE__ PRIVATE include)
endif()

ament_package()
