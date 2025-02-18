# Notes
Here I'll dump some random things that I think might come in handy
later on.

## Intel Goldmont datasheet notes
- Specific MSRs (not available in x86 manuals): [Datasheet page 3796 (Table 69-1)][gm_ds]
- Ball map: [Datasheet page 992][gm_ds]
- Pinout: [Datasheet page 995 - Table 39-1][gm_ds]

### UART
Chapter 18 (page 565)

Careful with MUX settings (Figure 18-2)

## Intel power management (PMC)
It's an ARC core, code is deployed together with ME (I believe). Some info on
how to forcibly update it [here](https://winraid.level1techs.com/t/how-to-update-pmc-code/36335/4)
as well as in the guide linked there.

Info on page 76 of pbx's [slides](https://pbx.sh/intelme_talk.pdf)

[Tweet from Ermolov](https://twitter.com/_markel___/status/978377825244925952/)

Maybe this Intel [doc](uefi-firmware-enabling-guide-for-the-intel-atom-processor-e3900-series.pdf)
can be useful. Info on UEFI image structure (reference to PMC).

ARCompact Ghidra plugin, [slides](https://www.sstic.org/media/SSTIC2021/SSTIC-actes/analyzing_arcompact_firmware_with_ghidra/SSTIC2021-Slides-analyzing_arcompact_firmware_with_ghidra-iooss.pdf)


[gm_ds]: Goldmont_c3000-family-datasheet-1623704.pdf