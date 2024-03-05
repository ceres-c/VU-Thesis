# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(PICO_PLATFORM rp2040)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)
set(PICO_SDK_PATH "/usr/share/pico-sdk")
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(PICO_BOARD pico CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

if (PICO_SDK_VERSION_STRING VERSION_LESS "1.4.0")
  message(FATAL_ERROR "Raspberry Pi Pico SDK version 1.4.0 (or later) required. Your version is ${PICO_SDK_VERSION_STRING}")
endif()

project(pmbus_inject_glitch_fw C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Check build env
if (NOT TARGET tinyusb_device)
  message(FATAL_ERROR "not building injector firmware because TinyUSB submodule is not initialized in the SDK")
endif()
if(NOT PICO_ON_DEVICE)
  message(WARNING "Not building injector firmware for Pico target. Are you sure you want to do this?")
endif()

# Add executable. Default name is the project name, version 0.1

add_executable(pmbus_inject_glitch_fw pmbus_inject_glitch_fw.c)

pico_set_program_name(pmbus_inject_glitch_fw "pmbus_inject_glitch_fw")
pico_set_program_version(pmbus_inject_glitch_fw "0.1")

pico_enable_stdio_usb(pmbus_inject_glitch_fw 1)
pico_enable_stdio_uart(pmbus_inject_glitch_fw 0)

# Add the standard library to the build
target_link_libraries(pmbus_inject_glitch_fw
  pico_stdlib
  hardware_i2c
  pico_i2c_slave
)

# Add the standard include files to the build
target_include_directories(pmbus_inject_glitch_fw PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}
  ${CMAKE_CURRENT_LIST_DIR}/.. # for our common lwipopts or any other standard includes, if required
)

pico_add_extra_outputs(pmbus_inject_glitch_fw)

