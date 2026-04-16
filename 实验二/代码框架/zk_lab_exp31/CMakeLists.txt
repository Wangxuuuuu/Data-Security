cmake_minimum_required(VERSION 3.16)
project(zk_lab_exp31 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(LIBSNARK_PREFIX "" CACHE PATH "Prefix where libsnark was installed")
if(NOT LIBSNARK_PREFIX)
  message(FATAL_ERROR "Set LIBSNARK_PREFIX, e.g. -DLIBSNARK_PREFIX=/path/to/deps/install")
endif()

set(LIBSNARK_INCLUDE_DIR "${LIBSNARK_PREFIX}/include")
set(LIBSNARK_LIB_DIR "${LIBSNARK_PREFIX}/lib")

# libsnark's installed headers still reference libfqfft headers via
#   #include <libfqfft/...>
# but libfqfft headers are not installed by default. We therefore add the
# in-tree include path.
set(LIBFQFFT_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/deps/libsnark/depends/libfqfft")
set(LIBSNARK_DEPS_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/deps/libsnark/depends")
set(LIBSNARK_BUILD_DEPS_LIB_DIR "${CMAKE_SOURCE_DIR}/deps/libsnark/build/depends")

include_directories(${LIBSNARK_INCLUDE_DIR})
link_directories(${LIBSNARK_LIB_DIR})
link_directories(${LIBSNARK_BUILD_DEPS_LIB_DIR})

add_executable(mysetup src/mysetup.cpp)
add_executable(myprove src/myprove.cpp)
add_executable(myverify src/myverify.cpp)

foreach(target mysetup myprove myverify)
  target_include_directories(${target} PRIVATE src ${LIBFQFFT_INCLUDE_DIR} ${LIBSNARK_DEPS_INCLUDE_DIR})
  target_compile_definitions(${target} PRIVATE CURVE_BN128 NDEBUG)
  target_link_libraries(${target} PRIVATE snark ff zm snark_supercop gmp gmpxx procps pthread ssl crypto)
endforeach()
