#!/usr/bin/env python3

import argparse
from functools import reduce
import struct
from math import floor
from hexdump import hexdump


HEADER_OFF = 0x30
HEADER_SIZE = 0x80
EXTRA_HEADER_SIZE_OFF = 0x34
REV_OFF = 0x3c
VCN_OFF = 0x40
REL_DATE_OFF = 0x8
DATE_OFF = 0x48
SIZE_OFF = 0x4c
CPU_SIG_OFF = 0x54
SEED_OFF = 0x90
SEED_SIZE = 0x20
RSA_MOD_OFF = 0xb0
RSA_MOD_SIZE = 0x100
RSA_EXP_OFF = 0x1b0
RSA_EXP_SIZE = 0x4
RSA_SIG_OFF = 0x1b4
RSA_SIG_SIZE = 0x100
ENC_UCODE_OFF = 0x2b4

UOP_BITMASK = 0xffffffffffff
SEQWORD_BITMASK = 0x3ff
OPCODE_BITMASK = 0xfff

# Code taken from CustomProcessingUnit/uasm-lib/ucode_parser.py
def parse_ucode_file(ucode: bytearray) -> int:
	'''
	Parses an Intel microcode update file and prints out some information.

	Returns the microcode size
	'''

	extra_header_size = struct.unpack("<H", ucode[EXTRA_HEADER_SIZE_OFF:EXTRA_HEADER_SIZE_OFF+2])[0]
	cpu_signature = struct.unpack("<I", ucode[CPU_SIG_OFF:CPU_SIG_OFF+4])[0]
	if (extra_header_size != 0xa1):
		print(f'  CPU: 0x{cpu_signature:x}')
		print(f'  extra_header_size: 0x{extra_header_size:x}')
		print('  [-] unsupported extra header size')
		return False

	ucode_patch_words = struct.unpack("<I", ucode[SIZE_OFF:SIZE_OFF+4])[0]
	ucode_patch_size = ucode_patch_words * 4
	ucode_size = ucode_patch_size - (ENC_UCODE_OFF - HEADER_OFF)

	ucode_revision = struct.unpack("<I", ucode[REV_OFF:REV_OFF+4])[0]
	ucode_version = struct.unpack("<I", ucode[VCN_OFF:VCN_OFF+4])[0]
	ucode_release_date = struct.unpack("<I", ucode[REL_DATE_OFF:REL_DATE_OFF+4])[0]
	ucode_date = struct.unpack("<I", ucode[DATE_OFF:DATE_OFF+4])[0]
	ucode_seed = ucode[SEED_OFF:SEED_OFF+SEED_SIZE]

	rsa_modulus = int(bytearray(reversed(ucode[RSA_MOD_OFF:RSA_MOD_OFF+RSA_MOD_SIZE])).hex(), 16)
	rsa_exp = struct.unpack("<I", ucode[RSA_EXP_OFF:RSA_EXP_OFF+RSA_EXP_SIZE])[0]

	rsa_sig = bytes(reversed(ucode[RSA_SIG_OFF:RSA_SIG_OFF+RSA_SIG_SIZE]))

	# Monkey patched using pycryptodome internal functions, maybe not the best long term solution...
	desc = ''
	desc += f'[.] CPU: 0x{cpu_signature:x}\n'
	desc += f'[.] size: 0x{ucode_size:x}\n'
	desc += f'[.] rev: 0x{ucode_revision:x}\n'
	desc += f'[.] VCN: 0x{ucode_version:x}\n'
	desc += f'[.] release date: {ucode_release_date & 0xffff :04x}-{(ucode_release_date >> 24) & 0xff :02x}-{(ucode_release_date >> 16) & 0xff :02x}\n'
	desc += f'[.] compilation date: {(ucode_date >> 16) & 0xffff:04x}-{(ucode_date >> 8) & 0xff:02x}-{(ucode_date) & 0xff:02x}\n'
	desc += f'[.] RC4 nonce: {ucode_seed.hex()}\n'
	desc += f'[.] RSA mod: {hex(rsa_modulus)}\n'
	desc += f'[.] RSA exp: {rsa_exp}\n'
	desc += f'[.] RSA sig: {rsa_sig.hex()}\n'
	print(desc)
	return ucode_size

# def crc_check(uop) -> str:
#     crc1 = reduce(f_parity, get_even_bits(uop & 0x3fffffffffff)) # Remove CRC from uop
#     crc2 = reduce(f_parity, get_odd_bits(uop & 0x3fffffffffff))
#     crc_ok = crc1 == ((uop >> 47) & 1) and crc2 == ((uop >> 46) & 1)
#     return '!' if not crc_ok else ''

BITMASKS = {
	'src0': 0b111111,
	'src1': 0b111111,
	'dst_src2': 0b111111,
	'imm1': 0b11111,
	'm0': 0b1,
	'imm0': 0b11111111,
	'opcode': 0b111111111111,
	'm1': 0b1,
	'm2': 0b1,
	'crc1': 0b1,
	'crc2': 0b1,
	'seqword': 0b1111111111
}

class Uop:
	def __init__(self, uop: int):
		self.src0 = uop & BITMASKS['src0']
		self.src1 = (uop >> 6) & BITMASKS['src1']
		self.dst_src2 = (uop >> 12) & BITMASKS['dst_src2']
		self.imm1 = (uop >> 18) & BITMASKS['imm1']
		self.m0 = (uop >> 23) & BITMASKS['m0']
		self.imm0 = (uop >> 24) & BITMASKS['imm0']
		self.opcode = (uop >> 32) & BITMASKS['opcode']
		self.m1 = (uop >> 44) & BITMASKS['m1']
		self.m2 = (uop >> 45) & BITMASKS['m2']
		self.crc1 = (uop >> 46) & BITMASKS['crc1']
		self.crc2 = (uop >> 47) & BITMASKS['crc2']
		self.seqword = (uop >> 48) & BITMASKS['seqword']
		self.seqword_chunk = (uop >> 48) # Keep all the upper bits. Don't know what they do beyond the 10th bit but yea...

		self.funcs = {
			'src0': self.xor_src0,
			'src1': self.xor_src1,
			'dst_src2': self.xor_dst_src2,
			'imm1': self.xor_imm1,
			'm0': self.xor_m0,
			'imm0': self.xor_imm0,
			'opcode': self.xor_opcode,
			'm1': self.xor_m1,
			'm2': self.xor_m2,
			'seqword': self.xor_seqword
		}

	def xor_src0(self, mask: int):
		self.src0 ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_src1(self, mask: int):
		self.src1 ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_dst_src2(self, mask: int):
		self.dst_src2 ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_imm1(self, mask: int):
		self.imm1 ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_m0(self, mask: int):
		self.m0 ^= mask
		self.crc2 ^= mask

	def xor_imm0(self, mask: int):
		self.imm0 ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_opcode(self, mask: int):
		self.opcode ^= mask
		self.crc1 ^= reduce(Uop.f_parity, Uop.get_odd_bits(mask))
		self.crc2 ^= reduce(Uop.f_parity, Uop.get_even_bits(mask))

	def xor_m1(self, mask: int):
		self.m1 ^= mask
		self.crc1 ^= mask

	def xor_m2(self, mask: int):
		self.m2 ^= mask
		self.crc2 ^= mask

	def xor_seqword(self, mask: int):
		raise NotImplementedError('seqword modification not implemented yet')

	def get_uop_int(self) -> int:
		return self.src0 | (self.src1 << 6) | (self.dst_src2 << 12) | (self.imm1 << 18) | (self.m0 << 23) | (self.imm0 << 24) | (self.opcode << 32) | (self.m1 << 44) | (self.m2 << 45) | (self.crc1 << 46) | (self.crc2 << 47) | (self.seqword_chunk << 48)
	
	def get_uop_bytes(self) -> bytes:
		return struct.pack("<Q", self.get_uop_int())

	@staticmethod
	def get_even_bits(v):
		bits = f'{v:048b}'
		return [int(i) for i in bits[::2]]
	@staticmethod
	def get_odd_bits(v):
		bits = f'{v:048b}'
		return [int(i) for i in bits[1::2]]
	@staticmethod
	def f_parity(a, b):
		return a ^ b

class Triad:
	def __init__(self, uop0: int, uop1: int, uop2: int):
		self.uop0 = Uop(uop0)
		self.uop1 = Uop(uop1)
		self.uop2 = Uop(uop2)
		self.uops = [self.uop0, self.uop1, self.uop2]
		self.seqword = (uop0 >> 48) & SEQWORD_BITMASK | (uop1 >> 48) & SEQWORD_BITMASK << 10 | (uop2 >> 48) & SEQWORD_BITMASK << 20

	def get_triad_bytes(self) -> bytes:
		return bytearray(self.uop0.get_uop_bytes() + self.uop1.get_uop_bytes() + self.uop2.get_uop_bytes())

if __name__ == '__main__':
	def auto_int(x):
		return int(x, 0)

	parser = argparse.ArgumentParser(description='Blind ucode bit fiddler')
	parser.add_argument('ucode', type=str, help='source ucode update file')
	parser.add_argument('target', type=str, choices=[k for k in BITMASKS if 'crc' not in k], help='Which part of the uop the mask will be applied to')
	parser.add_argument('-n', '--num', type=auto_int, default=0, help='0-based index of target uop to modify')
	parser.add_argument('-m', '--mask', required=True, type=auto_int, help='xor mask to apply')

	args = parser.parse_args()

	print(f'[+] {args.ucode}')
	with open(args.ucode, 'rb+') as f:
		ucode = bytearray(f.read())

		ucode_size = parse_ucode_file(ucode)

		c = 0 # cursor
		c += ENC_UCODE_OFF # Skip to the encrypted ucode
		c += 1 # Skip 0x01 ('initialize arrays')
		c += 1 # Skip 0x02 (marks start of ucode code that will be executed)
		c += 2 # Skip install address
		c += 2 # Skip patch size
		c += 24 * floor(args.num / 3) # Skip to the right triad
		t = Triad(*struct.unpack_from('<QQQ', ucode, c))

		if args.mask < 0 or args.mask > BITMASKS[args.target]:
			parser.error(f'uop mask must be between 0 and 0x{BITMASKS[args.target]:x}')
		print(f'[+] Original triad:{floor(args.num / 3)},uop:{args.num % 3}: 0x{t.uops[args.num % 3].get_uop_int():016x}')
		t.uops[args.num % 3].funcs[args.target](args.mask)
		print(f'[+] Modified triad:{floor(args.num / 3)},uop:{args.num % 3}: 0x{t.uops[args.num % 3].get_uop_int():016x}')

		f.seek(c)
		f.write(t.get_triad_bytes())
