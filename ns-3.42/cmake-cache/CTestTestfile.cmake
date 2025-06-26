# CMake generated Testfile for 
# Source directory: /home/andrei/ns-allinone-3.42/ns-3.42
# Build directory: /home/andrei/ns-allinone-3.42/ns-3.42/cmake-cache
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(ctest-stdlib_pch_exec "ns3.42-stdlib_pch_exec-debug")
set_tests_properties(ctest-stdlib_pch_exec PROPERTIES  WORKING_DIRECTORY "/home/andrei/ns-allinone-3.42/ns-3.42/cmake-cache/" _BACKTRACE_TRIPLES "/home/andrei/ns-allinone-3.42/ns-3.42/build-support/custom-modules/ns3-executables.cmake;47;add_test;/home/andrei/ns-allinone-3.42/ns-3.42/build-support/macros-and-definitions.cmake;1312;set_runtime_outputdirectory;/home/andrei/ns-allinone-3.42/ns-3.42/CMakeLists.txt;149;process_options;/home/andrei/ns-allinone-3.42/ns-3.42/CMakeLists.txt;0;")
subdirs("src")
subdirs("examples")
subdirs("scratch")
subdirs("utils")
