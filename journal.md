# Daily progress journal

## 2024-03-19
- Tried to get spispy to work, no dice really.

## 2024-03-20
- Modified Pi Pico board to run at 1v8, tested serprog and flashrom (working)
- Gave up with spispy as pi pico r/w cycle speed is good enough (~1m)

## 2024-03-21
- Got CPLD and BIOS update (CN22) header cable (1.27mm 2x6 flat), soldered on
ext board. Tested readout through CN22 (working)
- Started playing around with coreboot builds

## 2024-03-22
- Installed UART cable, kept on testing coreboot builds (not much luck)
- Extracted coreboot .config file from coreboot image given by lib-micro
authors, build works with video out. :)

## 2024-03-23
- Wasted half a day trying to get red unlock to work with my coreboot
- Discovered at my own expense that until you power flush the board, the intel
CSME will keep run the last firmware, even if you flash a new one.
POWER FLUSH THE BOARD!
- Started to thinker with coreboot to get fast boot times

## 2024-03-24
- Why is the thing discovered yesterday happening? Maybe it can be useful to
achieve faster boot times:
	flash red unlocked ME -> slow boot -> check success with `rdmsr 0x1e6`
	flash non-red unlocked ME -> boot quickly as long as we can read 0x1e6
- Reading exploit details to understand the above

## 2024-03-25
- Build coreboot payload to do `mul`s in a loop, similar to plundervolt PoC
- Turns out, there is no traffic on the PMBus when it's crunching numbers.
No need to touch the PMC firmware! :)

## 2024-03-26
< Day off >

## 2024-03-27
- Wasted one full day on exception handling on x86 (I am mentally challenged)
to perform MSR detection. If magic MSR is readable, the CPU is red unlocked and
we don't need to install the slow ME firmware. If not, load red unlocked ME.

## 2024-03-28
- Got General Protection Fault handler to work, found the right part of the
codebase to insert the MSR check. Now to test it.

## 2024-03-29
- Find out how to modify coreboot build system to include both ME firmwares.

## 2024-03-30
< Day off >

## 2024-03-31
- Found out that with the stock BIOS the GPIO header works out of the box
(tested the UART in ubuntu). It does not work in linux with coreboot or
slimbootloader. How is the original BIOS setting the GPIOs?
- Actually, coreboot can output on the GPIOs! How to init it in my payload?

## 2024-04-01
- Turns out that actually GPIOs don't work in coreboot, I only forgot to power
cycle the board and thus the FPGA still had the bitstream from the original
BIOS.

## 2024-04-02
< Day off >

## 2024-04-03
- Temporarily ignore GPIO/UART thing, focus on ME firmware
- Use coreboot FSP_2 setting, expand it to apollolake architecture

## 2024-04-04
- Turns out the FSP is always loaded by the CPU before my code is even executed
No way to change the ME firmware from coreboot. :(
- Maybe this is good: I can always use the red unlocked ME firmware, as it will
stall only later and move my payload to coreboot's romstage

## 2024-04-05
< Day off >

## 2024-04-06
- Verified that the msr is readable in early bootstage

## 2024-04-07
- Read up about CustomProcessingUnit/lib-micro internals

## 2024-04-08
- Trying to merge lib-micro in coreboot

## 2024-04-09
< Day off >

## 2024-04-10
- Trying to integrate lib-micro in coreboot. Fail

## 2024-04-11
- Libmicro working in linux 32bit binary
- Not working in coreboot, it writes URAM, but can't invoke arb. ucode

## 2024-04-12
< Day off >

## 2024-04-13
< Day off >

## 2024-04-14
< Day off >

## 2024-04-15
- Managed to run libmicro in coreboot in chip.c `platform_fsp_notify_status`:
`phase == READY_TO_BOOT`. This takes ~10s to run, but it works!

## 2024-04-16
- Managed to run libmicro in coreboot at the end of `soc_init` in ramstage: ~1s

## 2024-04-17
- Apparently `set_power_limits` must be called before any ucode injection
is done. Idk why, as it seems to be doing only power-related stuff
- I could (not tried) move my code to early bootblock, but that requires doing
something with `BIOS_RESET_CPL`, idk...
- Code cleanup
- Add some pi pico sync stuff around the hijacked opcode

## 2024-04-21
- Pi pico firmware sync stuff

## 2024-04-22
- Got the sync to work properly (issues with UART not being ready to be read
when the ISR was called)
- Tested the setup without actual fault injection, seems ok.
- It seems that the Intel CPU is running at a rather low ~16MHz. I measured the
time between two consecutive `R` sent by the target with the logic analyzer,
and they were 579,96273 ms apart. According to binja, 9 instructions are
executed per cycle, and there are 1000000 cycles. That means:
$$\left(\frac{579,96273 \ \text{ms}}{1000000 * 9}\right)^{−1} \approx 15,5 \ \text{Hz}$$

## 2024-06-05
- Writing code to retreive delay loop duration on target from pi pico

## 2024-06-06
- Writing code to calculate target UART TX -> pico UART RX delay
- Done obtaining relevant delays, I guess

## 2024-06-13
- Writing code to identify stable threshold voltages
- Switched power supply to lab psu for easy target reset

## 2024-06-14
- Reliable code
- Found some weird behavior with target dying after a while (see images in
notebooks/img)
- Above looks similar to when I power the target on and it is simply not
brought up entirely, that is without any fault injection going on. It just
boots, does its thing for a couple of ms, then hangs. Probs it does not like
the ME being only half loaded or something.

## 2024-06-15
- Moved glitch success detection to target side, as it is faster (and easier to
find the right moment to glitch)
- Added Vp preparation voltage config
