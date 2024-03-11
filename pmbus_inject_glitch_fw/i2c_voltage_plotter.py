#!/usr/bin/env python

import serial

CMD = {
	'PING'				: b'P',
	'CMD_GET_I2C_VCORE'	: b'v',
}
RESP = {
	'OK'				: b'k',
	'KO'				: b'x',
	'PONG'				: b'p',
}

def main() -> int:
	try:
		s = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=0.1)
	except Exception as e:
		print(f'[!] Could not open serial port. Got:\n{e}\nAborting.')
		return 1

	s.write(CMD['PING'])
	r = s.read(len(RESP['PONG']))
	if r != RESP['PONG']:
		print(f'[!] Could not ping the device. Got:\n{r}\nAborting.')
		exit(1)
	print('[+] Device available.')

	prev = None
	while True:
		s.write(CMD['CMD_GET_I2C_VCORE'])
		r = s.read(1)
		if not r:
			continue
		val = r[0]
		if val == prev:
			continue
		print(f'[+] Voltage: 0x{val:02x}')
		prev = val

	return 0

if __name__ == "__main__":
	exit(main())
