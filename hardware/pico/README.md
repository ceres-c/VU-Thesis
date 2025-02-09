# Pico Glitcher (Picocoder)

These boards have been used for FI experiments on Intel CPUs. See `firmware/pico/README`
for instructions about the Pico firmware.

## Variants

In this folder you will find the schematics of:

- `Glitcher-v1`: Unmodified Pico with level shifters for the PMBus output
- `Glitcher-v2`: Modded Pico that runs at 18.V

## Voltage levels

Intel CPUs talk with external devices at 1.8V, and that includes both the
PMIC (over PMBus) and the BIOS EEPROM (over SPI). Additionally, the UART on the
UP Squared board is 3.3V.

The Pico runs at 3.3V by default, so you can either modify it to run at 1.8V
(see the RP2040 datasheet §2.9.7.3) or shift down PMBus and SPI. If you convert
the Pico to 1.8V, you will need to use a level shifter for the UART. TXS0102
and TXS0108 should work.

### UART

Pico pinout for the UART is as follows:

| GPIO | Pico Pin | Function |
| ---- | -------- | -------- |
| 0    | 1        | TX       |
| 1    | 2        | RX       |

### Flash

Additionally, this board can be used to flash Coreboot on the Flash ROM of
your target.

Pico pinout for connecting to FLash is as follows:

| GPIO | Pico Pin | Function |
| ---- | -------- | -------- |
| 22   | 29       | CS       |
| 26   | 31       | SCK      |
| 27   | 32       | MOSI     |
| 28   | 34       | MISO     |

## Schematics

- [Glitcher-v1](glitcher-v1/schematic.pdf)
- [Glitcher-v2](glitcher-v2/glitcher-v2.pdf)
