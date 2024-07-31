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

## 2024-06-17
- Some more testing

## 2024-06-18
- Looked up alternative boards for Plundervolt/Voltpillager

## 2024-06-23
- I see something interesting, sometimes the loop duration is shorter. Is the
voltpillager-like loop with a lot of jumps a problem? Am I breaking the jump or
the muls?
- Unrolled the loop, it seems that loops are getting shorter but I always get
`R` instead of `S` as I would expect when a mul is actually glitched (?)

## 2024-06-24
- Found some partial success? The board reports two different results for the
muls, but it hangs after the first byte is sent. Try adding delays?

## 2024-06-25
- Added delay after the mul loop is done to allow the voltage to be restored
after the glitch and before the UART peripheral is used. Maybe the CPU is
browning out due to that beign turned on?
- Expanded search space and just left the glitching running for a while:
SUCCESS!

## 2024-06-27
- Improved python code for readabilty
- Wrote headless code for data collection
- It seems that both `imul 0x80000, 0x4` and `imul 0x4, 0x80000` can be
glitched, but Plundervolt's paper mentions they never had success with the
latter. Weird?

## 2024-06-28
- Seems like on my CPU, FIT installs the updated ucode on all cores. On some
other CPUs, it only installs it on the BSP (Boot Strap Processor). This might
be interesting for software-based attacks on those CPUs (?)
Source: https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/best-practices/microcode-update-guidance.html#inpage-nav-undefined-undefined

## 2024-06-29
- Alvise probably found the reason for half success: at that stage coreboot has
not fully populated the IDT, thus when an exception is thrown it just hangs.
Probably when I get a half success the CPU is just in some weird state that
will eventually throw an exception down the line due to some corrupt stack
write or something.
- Well, it turns out that if I run on the target code that only relies on
registers instead of stack, I don't get *any* glitch. (:
I suppose I was glitching some memory access before? Not muls.

## 2024-06-30
- Collecting data points for stackless code. Some weak half success somewhere
with small width, idk.
- Improved db plotter with separate plots for different aspects (one set for
each voltage...)
- Improved python control code to check if settings can actually be achieved
by PMIC (due to low slew rate). It prints/raise exceptions if settings are not
feasible.

- Seems like on my CPU, FIT installs the updated ucode on all cores. On some
other CPUs, it only installs it on the BSP (Boot Strap Processor). This might
be interesting for software-based attacks on those CPUs (?)
Source: https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/best-practices/microcode-update-guidance.html#inpage-nav-undefined-undefined

## 2024-06-29
## 2024-07-01
- Tested wider Vp and Vf ranges with stackless code, no success. I estimated
Vp setting Vf to 1.24V (nominal VCore), and lowering Vp alone. The target is
stable up to VID 35, below that I get glitches. I then used Vp in the range
[30:35] and Vf in the range [1.24:1.28] and got no glitches. I then used Vp in
[20:35], but no dice.
- Started to read into Intel Firmware Support Package (FSP) to validate which
caches are available and used as RAM.
	- Verified this CPU uses FSP v2.0.
		Source: Apollolake Intel(R) Firmware Support Package (FSP) Integration Guide $ 3
		Source: coreboot/src/soc/intel/apollolake/Kconfig - PLATFORM_USES_FSP_2_0
	- romstage boots from
		- src/cpu/x86/entry32.S
		- src/soc/intel/common/block/cpu/car/cache_as_ram.S
	- In cache_as_ram.S, it configures CAR to use L2 cache as RAM because it
	checks the cache ram size, and it is defined to be 768 KB in
	src/soc/intel/apollolake/Kconfig
	L1d cache is 24KB, L1i cache is 32KB, L2 cache is 2 MB (source: Intel Atom
	Processor C3000 Product Family Datasheet), so the only cache that can be
	in use as RAM is the L2 cache.

## 2024-07-02
- CAR area is configured as Write Back (WB) cacheable and non evictable
	- src/soc/intel/common/block/cpu/car/cache_as_ram.S
- INTEL_CAR_CQOS is enabled, which enables Cache Quality of Service (CQoS) to
"allows more fine-grained control of cache usage. As result, it is possible to
set up a portion of L2 cache for CAR and use the remainder for actual caching."
Source: Coreboot kconfig option description
	- CQOS mode also disables L1 and L2 prefetchers on line 376
	- OR DOES IT? It is then enabled again at 440
- After CAR is enabled, it jumps to `car_init_done` and finally
`bootblock_c_entry`.

## 2024-07-03
- Load-heavy target code can be *very* easily glitched, but the results I get
over UART are weird. I get >0 successful glitches, but the faulted values
are either 0xAAAAAAAA (the standard value) or 0x00000000 (initialization
value).
	- Actually sometimes I have 0xAAAAAA00/0xAAAA0000, which is interesting
	but max 0.3% of the times.
	- Good parameters are
```bash
python3 data_collector.py glitch2.db <table name> load --ext-offset 90 150 1 --prep-voltage 36 36 1 --width 10 30 1 --voltage 35 35 1
```
- VCC controls VCore and also L1/L2 cache voltage (they are part of the core)
Source: "The Forgotten ‘Uncore’: On the Energy-Efficiency of Heterogeneous Cores"
by 5 intel people

## 2024-07-04
- Verified that old mul target is also glitchable with the same parameters I
have found for the load target. Target code just did not run for long enough,
so the voltage was still low at the end of the loop, and the CPU died. I
increased the loop duration and got glitches there as well, this means that
all my tests are consistent.

## 2024-07-05
- Started to play around with ucode patching + studied uopcode "documentation"

## 2024-07-06
- Patched `rdrand` to perform (`ecx += eax != ebx`):
	```
	tmp0 = eax - ebx
	if (tmp0 == 0) ecx += 1
	```
Works in both 64 and 32 bit code with libmicro on linux
- Added this code in coreboot, target CPU hangs after "some" short amount of
time

## 2024-07-07
- Determined that the CPU hangs only when I have a conditional jump in ucode
- Tried to make conditional seqwords work. No luck (maybe I am stupid)
- Changed ucode to perform (`ecx += eax - ebx`):
	```
	tmp0 = eax - ebx
	ecx += tmp0
	```
- Found glitces in ucode! :D
Params:
```bash
python3 data_collector.py glitch2.db _6a234f1_customucode cmp --ext-offset 90 150 1 --prep-voltage 34 36 1 --width 1 30 1 --voltage 32 34 1
```

## 2024-07-08
- Target now sends the result of any operation to the glitcher, to get rid of
the if statement at the end of each loop iteration.
- Tried same parameters that worked with cmp and got same results
- Tried same parameters that gave me good results with rdrand and it seems
to be kinda slower because it crashes more often (?). Same amount of glitches
though, it seems

## 2024-07-09
- Noticed sometimes the target sends back a coreboot debug message after
glitch. Changed code to send it to the host.

## 2024-07-10
- Found relatively good parameters for rdrand-sub glitching (12 successes in 
~5:30h)
```bash
python3 data_collector.py glitch2.db _0d0af5f_customucode_7 rdrand-sub --ext-offset 70 120 1 --prep-voltage 49 49 1 --width 27 27 1 --voltage 33 33 1
```

## 2024-07-11
- Patched rdrand to do `rcx += 1`
	- Found glitches easily, see table `_3b850a7_customucode_add`
	- I have mostly values <120000, but also some are way higher (2058130387).
	Values <120000 can be explained with instruction skips, but how about the
	other ones? Is this same behavior as rdrand-sub glitches, maybe? Less
	frequent than instrucion skips, but still there every now and then.
	- Above is coherent with the *huge* amount of glitches I get with cmp-sete
	assembly code I had at start: architectural instruction fetches are easier
	to skip than ucode is to glitch in some other way.
- Patched rdrand to do `rcx += 1` 10 times in a row (aka `rdrand := ecx += 10`)
	- I only get values modulo 10, so it seems that the CPU is not executing
	the whole rdrand instruction, not skipping only ONE uop. Unlucky.
- SEE MESSAGES FROM 2024-07-11 FROM 22:26 TO 23:30 ON SLACK. IMPORTANT STUFF


## 2024-07-14
- Created register-heavy target. Tested in linux to be working, kills the CPU
in coreboot.
- Also I don't know why exception handlers don't work? IDT_IN_EVERY_STAGE is
enabled in kconfig, but even 1/0 just hangs the cpu

## 2024-07-15
- Fixed exception handling in coreboot. Something related to multicore stuff in
ramstage (I don't have multicore yet)
- ucode still broken

## 2024-07-16
- ucode registers-heavy fixed: turns out you can't use MOVE in protected mode,
but ZEXT works.
- ucode cmp: implemented with SETCC instead of jumps. I guess?
- ucode cmp: can't get jumps to work. As soon as I try to do a conditional
jump, the CPU hangs. I have even tried to jump to the standard rdrand code, but
it still hangs. I have no idea why.
- Started playing around with register-heavy target. I got a couple of glitches
but nothing major. Is the register renamer tricking me here?
	- How do you prevent it from doing its job? Maybe Agner's paper has some
	info on that?

## 2024-07-17
- Reading Agner's microarchitecture paper, Goldmont is good for a couple of
reasons:
	- §16.5 Macro-op fusion:
		> There is no Macro-op fusion

		This is nice because, I would assume, makes stuff easier to glitch
		at uop level. We might have higher chance of glitching smaller
		uop chunks, maybe?

	- §16.6 Special cases of independence:
		> The processor **recognizes that xor instructions are independent**
		> of the prior value of the register if the two input operands are the same register. This works
		> with 32- and 64-bit registers, mmx, and xmm registers. **It does not work for subtract,**
		> **compare, or other instructions.**

		This should help me with register-heavy target. Maybe I can use OR 0 or
		something like that? Add 0? Preferably OR as it should be smaller in
		ALU

	- §16.7 Execution units
		> Register-to-register moves **can be eliminated be register renaming** for 32- and 64-bit
		> registers
	
		Yea, shit. Should find a way to prevent register renaming, I guess.
		Maybe OR with 0?

- Is register renaming a thing with ucode temp registers as well? I'd say so,
but who knows?
- After a full night of testing, I am getting a low success ratio. I  think
register renaming is trolling me.
	- Might want to use OR instead of MOVE, as stated above

- Pietro published an easier to follow sketch of the update process here:
https://github.com/pietroborrello/CustomProcessingUnit/blob/master/Notes.md#ucode-update

- He refers to this header, which in turn expands on Ben Hawkes findings:
https://github.com/platomav/MCExtractor/wiki/Intel-Microcode-Extra-Undocumented-Header

- Current ucode revision in FIT image is 0x20
- Current ucode revision in coreboot's cbfs is 0x28

## 2024-07-18
- Ucode file rev 0x28 that is actually loaded is: 06-5c-0a

## 2024-07-19
- HMMMM RC4 is a keystream, does not depend on the ciphertext/plaintext, can I
flip bytes in ciphertext and get flips in plaintext? (yes)
- Found new idea: identify valid bitflipped uops/target/source registers in
ucode and flip the right bit in CRC as well, so I have "legal" ucode that does
something different. Then, if I can glitch the RSA signature verification, I
have successfully loaded custom ucode. :D

## 2024-07-20
< Worked on PhD application >

## 2024-07-21
- I have code to arbitrarily flip bits in opcodes from the ciphertext, and the
decrypted ucode will have the correct CRC
- Now that I think of it, I can technically encode any opcode in the encrypted
ucode. Applying the right xor mask to the ciphertext will give valid
(decrypted) opcodes.
- Seems that the first invocation of the ucode update process takes more cycles
than the following ones (when the ucode is already updated).
	- 1st round: ~6193516 cycles
	- 2nd round: ~5785233 cycles

## 2024-07-22
- Turns out the ucode update is not copied to L2 cache, but some SRAM used for
power state C6: https://x.com/_markel___/status/1723000519138988538

## 2024-07-28
- Tried to make a re-encrypted ucode file with another legal opcode instead of
NOP, but I don't get any success...

## 2024-07-30
- Switched to RSA mod flipping. Changed byte at position `0xb0` from `0xb1` to
`0xb0`.
	- Original update file takes (median):		6166414 clock cycles
	- Update with RSA changed takes (median):	4375847 clock cycles
- I got some glitches with the RSA flipped ucode :D
	ext_offset=3650:3800(1),width=200:230(1),voltage=31,prep_voltage=37:38(1)
	(see table _90ec1b5_ucode_update_rsamod_4)
	- Runtime: 1913.54s
	- This code reports only the time it took to do the update.
- Changed target code to return both final ucode version and the time it took
to update it. This way I can see if the update was successful or not.
	- Now the same settings don't work anymore :(

## 2024-07-31
- Left it running all night expanding the search space. Found some successes,
of which many were just issues with UART code, I'd say (wrong ucode revision)
or wild time measurements. Some were actually valid ucode revisions and
sensible update times (in the ballpark of an update on top of the same ucode).
(see table _90ec1b5_ucode_update_rsamod_6)
	- Runtime: 34180.64s
	- Also note, I have table _90ec1b5_ucode_update_rsamod_6_copy where I
	filtered out the unlikely results
- Found sweet spot, it's before the one I found yesterday, but same success rate 
	ext_offset=3570:3590(1),width=150:250(1),voltage=30:31(1),prep_voltage=36:40(1)
	(see table _90ec1b5_ucode_update_rsamod_7)
	- Runtime: 564.00s
- 
