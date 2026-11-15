cmake_minimum_required(VERSION 3.16)
project(eurobot_common)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(eurobot_interfaces REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# contract.yaml -> contract.hpp / contract.py (regenerated whenever the yaml changes)
set(gen_dir ${CMAKE_CURRENT_BINARY_DIR}/gen)
set(gen_hpp ${gen_dir}/include/eurobot_common/contract.hpp)
set(gen_py ${gen_dir}/contract.py)
set(gen_script ${CMAKE_CURRENT_SOURCE_DIR}/scripts/gen_contract.py)
set(contract ${CMAKE_CURRENT_SOURCE_DIR}/contract.yaml)
add_custom_command(
  OUTPUT ${gen_hpp} ${gen_py}
  COMMAND ${CMAKE_COMMAND} -E make_directory ${gen_dir}/include/eurobot_common
  COMMAND ${Python3_EXECUTABLE} ${gen_script} ${contract} --cpp ${gen_hpp}
  COMMAND ${Python3_EXECUTABLE} ${gen_script} ${contract} --py ${gen_py}
  DEPENDS ${contract} ${gen_script}
  COMMENT "Generating interface contract")
add_custom_target(${PROJECT_NAME}_contract ALL DEPENDS ${gen_hpp} ${gen_py})

add_library(${PROJECT_NAME} INTERFACE)
add_dependencies(${PROJECT_NAME} ${PROJECT_NAME}_contract)
target_include_directories(${PROJECT_NAME} INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${gen_dir}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>)
target_link_libraries(${PROJECT_NAME} INTERFACE
  rclcpp::rclcpp ${eurobot_interfaces_TARGETS})

install(DIRECTORY include/ ${gen_dir}/include/ DESTINATION include/${PROJECT_NAME})
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME})
install(FILES contract.yaml DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/gen_contract.py scripts/contract_check DESTINATION lib/${PROJECT_NAME})

ament_python_install_package(${PROJECT_NAME})
install(FILES ${gen_py} DESTINATION ${PYTHON_INSTALL_DIR}/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_gtest(test_contract test/test_contract.cpp)
  target_link_libraries(test_contract ${PROJECT_NAME})
  ament_add_pytest_test(test_gen_contract test/test_gen_contract.py)
endif()

ament_export_targets(export_${PROJECT_NAME})
ament_export_dependencies(rclcpp eurobot_interfaces)
ament_package()
