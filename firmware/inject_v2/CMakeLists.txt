cmake_minimum_required(VERSION 3.13)
# initialize the SDK based on PICO_SDK_PATH
# note: this must happen before project()
include(pico_sdk_import.cmake)
project(picocoder)

pico_sdk_init()

add_executable(picocoder)

pico_generate_pio_header(picocoder ${CMAKE_CURRENT_LIST_DIR}/pio/spi.pio)

target_sources(picocoder PRIVATE
        main.c
        # PIO components
        pio/pio_spi.c
        )

target_link_libraries(picocoder PRIVATE pico_stdlib hardware_pio)
pico_add_extra_outputs(picocoder)

# enable usb output, disable uart output
pico_enable_stdio_usb(picocoder 1)
pico_enable_stdio_uart(picocoder 0)
