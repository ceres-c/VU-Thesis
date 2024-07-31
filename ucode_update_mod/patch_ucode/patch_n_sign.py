#!/usr/bin/env python3
import argparse
import struct

from hashlib import sha256

# pycryptodome
from Crypto.PublicKey import RSA
import Crypto.Util.number as CUN

from custom_sha import generate_hash

INTEL_RSA_LEN = 2048
INTEL_RSA_EXP = 0x11

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

# The following 4 functions are taken from CustomProcessingUnit's ucode_parser.py, as well as some code below
def KSA(key):
	keylength = len(key)
	S = bytearray(range(256))
	j = 0
	for i in range(256):
		j = (j + S[i] + key[i % keylength]) % 256
		S[i], S[j] = S[j], S[i]  # swap
	return S
def PRGA(S):
	i = 0
	j = 0
	while True:
		i = (i + 1) % 256
		j = (j + S[i]) % 256
		S[i], S[j] = S[j], S[i]  # swap
		K = S[(S[i] + S[j]) % 256]
		yield K
def RC4(key):
	S = KSA(key)
	return PRGA(S)
def sha(b):
    h2 = sha256()
    h2.update(b)
    return h2.digest()

def get_priv_key(filename: str) -> RSA.RsaKey:
	'''
	Returns the RSA private key from the file, or generates a new one and saves it to the file.
	'''
	# Check if we can find the file update_key
	try:
		with open(filename, 'rb') as f:
			privkey = RSA.import_key(f.read())
			assert privkey.e == INTEL_RSA_EXP
	except FileNotFoundError:
		# Generate a new key and save it to update_key
		# Both modulus and exponent are checked in the ucode update procedure, we will glitch the exponent check
		privkey = RSA.generate(bits=INTEL_RSA_LEN, e=INTEL_RSA_EXP)
		with open(filename, 'wb') as f:
			f.write(privkey.export_key())
	return privkey

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Generate a patched and signed (with custom key) ucode update file')
	parser.add_argument('update_file', type=str, help='ucode update file to patch and sign')
	parser.add_argument('-k', '--key-file', type=str, help='RSA private key file for signing the update file (created if does not exist)', default='update_key')
	args = parser.parse_args()

	# Read the ucode update file
	with open(args.update_file, 'rb') as f:
		ucode = bytearray(f.read())

	# Retrieve some info
	ucode_patch_words = struct.unpack("<I", ucode[SIZE_OFF:SIZE_OFF+4])[0]
	ucode_patch_size = ucode_patch_words * 4
	ucode_size = ucode_patch_size - (ENC_UCODE_OFF - HEADER_OFF)
	ucode_seed = ucode[SEED_OFF:SEED_OFF+SEED_SIZE]
	GLM_secret = bytes.fromhex('0E 77 B2 9D 9E 91 76 5D A2 66 48 99 8B 68 13 AB')
	seed = GLM_secret + ucode_seed + GLM_secret

	rc4_key = b''
	h = seed
	for i in range(8):
		h = generate_hash(seed, padding=False, result_endianess='little', update=(i != 0))
		rc4_key += h

	keystream = RC4(rc4_key)
	# dump the first 0x200 bytes
	for k in range(0x200):
		next(keystream)

	decrypted = b''
	full_key = b''
	for b in ucode[ENC_UCODE_OFF: ENC_UCODE_OFF + ucode_size]:
		k = next(keystream)
		decrypted += bytes([b ^ k])
		full_key += bytes([k])

	decrypt_sha = bytes(reversed(sha(ucode[HEADER_OFF: HEADER_OFF + HEADER_SIZE] + decrypted)))

	# Do RSA signing
	privkey = get_priv_key(args.key_file)
	pubkey = privkey.public_key()
	privkey_mod_bits = CUN.size(privkey.n)
	signature = privkey._decrypt_to_bytes(CUN.bytes_to_long(decrypt_sha))

	# Check if the signature is correct
	pubkey_mod_bits = CUN.size(pubkey.n)
	k = CUN.ceil_div(pubkey_mod_bits, 8) # Convert from bits to bytes
	plain_rsa_sig = CUN.long_to_bytes(pubkey._encrypt(CUN.bytes_to_long(signature)), k)

	assert(decrypt_sha == plain_rsa_sig[-32:])
	print(f'RSA exp: {pubkey.e}')
	print(f'RSA mod: {hex(pubkey.n)}')
	print(f'RSA sig: {signature.hex()}')	

	print(f'Writing patched and signed ucode update file to {args.update_file}_signed')
	signature_for_update_file = bytearray(reversed(signature))
	modulus_for_update_file = bytearray(reversed(CUN.long_to_bytes(pubkey.n, INTEL_RSA_LEN//8)))
	with open(args.update_file + '_signed', 'wb') as f:
		f.write(ucode)
		f.seek(RSA_SIG_OFF)
		f.write(signature_for_update_file)
		f.seek(RSA_MOD_OFF)
		f.write(modulus_for_update_file)
