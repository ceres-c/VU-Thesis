# Intel picocoder

This is a Raspberry Pi Pico firmware to perform voltage fault injection attacks
on Intel CPUs (Goldmont) microcode. It communicates with the target board via
UART0 (see [coreboot docs][coreboot-up-squared-doc]), and expects the target to
be red unlocked, and running the modified coreboot image that injects the
custom microcode at boot in ramstage.

Additionally, this firmware can be used as a generic SPI flash programmer using
the serprog protocol. The code to do so is pulled straight from
Tomas Roth's [pico-serprog](https://github.com/stacksmashing/pico-serprog).

See `hardware/pico/README.md` to know how to connect the hardware to the
target.

## Building & Flashing

```bash
rm -rf build; (mkdir build && cd build && cmake ..)
(cd build && make && picotool load -f picocoder.uf2 && picotool reboot)
```

## Usage

TODO

See [pico-serprog][pico-serprog] readme for usage instructions as SPI flasher

[coreboot-up-squared-doc]: https://doc.coreboot.org/mainboard/up/squared/index.html
[pico-serprog]: https://github.com/stacksmashing/pico-serprog
