#! /usr/bin/env python3

from collections import defaultdict
from itertools import combinations_with_replacement, product
from pathlib import Path
from typing import Iterable

OPCODE_BITS = 12

def read_file(path: str|Path) -> tuple[dict, dict]:
	'''
	Returns a tuple of two dictionaries.
	The first dictionary maps opcode IDs to mnemonics, and the second dictionary maps mnemonics to opcode IDs.
	'''

	g_opcodes = {}
	g_opcodes_to_id = {'NOP': 0}

	with open(path, "r") as fi:
		for line in fi:
			opcode_mnem = line.split(":")
			if opcode_mnem[0] == "":
				assert(len(opcode_mnem) == 1)
				continue
			assert(len(opcode_mnem) == 2)
			g_opcodes[int(opcode_mnem[0], 16)] = opcode_mnem[1].strip()
			g_opcodes_to_id[opcode_mnem[1].strip()] = int(opcode_mnem[0], 16)

	return g_opcodes, g_opcodes_to_id

def tuple_to_int(bitlist: Iterable[int]) -> int:
	out = 0
	for bit in bitlist:
		out = (out << 1) | bit
	return out

def main() -> int:
	g_opcodes, _ = read_file(Path(__file__).parent / "opcodes.txt")
	matched_opcodes = defaultdict(set)

	xormasks = [tuple_to_int(t) for t in product([0, 1], repeat=OPCODE_BITS)]
	for opcode in g_opcodes:
		for xormask in xormasks:
			xor_opcode = opcode ^ xormask
			if xor_opcode in g_opcodes:
				matched_opcodes[opcode].add((xor_opcode, xormask))

	for opcode, matches in matched_opcodes.items():
		print(f'{g_opcodes[opcode]} => {len(matches)} matches')
		# print(f"{g_opcodes[opcode]} ({opcode:03x}):")
		# for match, xormask in matches:
		# 	print(f"  {g_opcodes[match]} (0x{match:03x}) ^ 0x{xormask:03x} = 0x{opcode:03x}")

	return 0

if __name__ == "__main__":
	exit(main())
