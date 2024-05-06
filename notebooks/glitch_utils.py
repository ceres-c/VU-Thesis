import random
import struct
from enum import Enum
from itertools import product
from typing import Annotated, Iterator

import serial

P_CMD_ARM					= b'\x20'
P_CMD_DISARM				= b'\x21'
P_CMD_SET_EXT_OFFST			= b'\x22'
P_CMD_SET_WIDTH				= b'\x23'

P_CMD_ARM					= b'\x20'	# Enable glitch handler
P_CMD_DISARM				= b'\x21'	# Disable glitch handler
P_CMD_FORCE					= b'\x22'	# Force write to PMBus to perform a glitch
P_CMD_SET_VOLTAGE			= b'\x23'	# Set glitch voltage
P_CMD_SET_EXT_OFFST			= b'\x24'	# Set external offset (wait after trig.) in us
P_CMD_SET_WIDTH				= b'\x25'	# Set glitch width	(duration of glitch) in us

P_CMD_RESULT_RESET			= b'\x50'	# Target reset
P_CMD_RESULT_ALIVE			= b'\x51'	# Target alive (data will follow)
P_CMD_RESULT_DEAD			= b'\x52'	# Target dead
P_CMD_RESULT_ZOMBIE			= b'\x53'	# Target is nor alive nor it reset after glitch
P_CMD_RESULT_DATA_TIMEOUT	= b'\x54'	# Target timeout after glitch when sending data back (target is alive)
P_CMD_RESULT_UNREACHABLE	= b'\x55'	# Target unavailable when starting glitch: did not receive anything on the serial port
P_CMD_RESULT_UNCONNECTABLE	= b'\x56'	# Target unavailable when starting glitch: did not receive the expected connection command
P_CMD_RESULT_UNTRIGGERED	= b'\x57'	# No trigger received after connection was established
P_CMD_RESULT_PMIC_FAIL		= b'\x58'	# Could not send command to PMIC

P_CMD_RETURN_OK				= b'\x61'	# Command successful
P_CMD_RETURN_KO				= b'\x62'	# Command failed
P_CMD_PONG					= b'\x63'	# Response to ping

P_CMD_PING					= b'\x70'	# Ping picocoder

class GlitchResult(str, Enum): # str is needed to allow the enum to be a dict key (for the legend)
	RESET			= 0
	NORMAL			= 1
	WEIRD			= 2
	SUCCESS			= 3
	BROKEN			= 4
	DEAD			= 5

def result_to_marker(result: GlitchResult) -> str:
	'''
	Convert a GlitchResult to a matplotlib-compatible scatter plot marker
	'''
	dic = {
		GlitchResult.RESET: 'xr',
		GlitchResult.NORMAL: '1b',
		GlitchResult.WEIRD: '<y',
		GlitchResult.SUCCESS: 'og',
		GlitchResult.BROKEN: 'Dm',
		GlitchResult.DEAD: 'sk',
	}
	return dic[result]

class GlitchController:
	def __init__(self, groups: list[str], parameters: list[str]):
		self.groups = groups
		self.params = {param: {'start': 0, 'end': 0, 'step': 1} for param in parameters}
		self.results: list[tuple[tuple[int, ...], GlitchResult]] = []

	def set_range(self, param: str, start: int, end: int) -> None:
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['start'] = start
		self.params[param]['end'] = end

	def set_step(self, param: str, step: int) -> None:
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['step'] = step

	def rand_glitch_values_inf(self) -> Iterator[tuple[int, ...]]:
		'''
		Generates an infinite sequence of random glitch values
		'''
		while True:
			yield tuple(random.randrange(param['start'], param['end'] + 1, param['step']) for param in self.params.values())

	def rand_glitch_values(self) -> Iterator[tuple[int, ...]]:
		'''
		Generates a finite sequence of random glitch values covering the entire parameter space exactly once
		NOTE: Highly inefficient for large parameter spaces
		'''
		combinations = list(product(
			*(range(param['start'], param['end'] + 1, param['step']) for param in self.params.values())
		))
		random.shuffle(combinations)
		for combination in combinations:
			yield combination


	def add_result(self, glitch_values: tuple[int, ...], result: GlitchResult):
		self.results.append((glitch_values, result))

class GlitchyMcGlitchFace:
	s: serial.Serial = None # type: ignore

	# Locally cached properties
	_ext_offset: int = None # type: ignore
	_width: int = None		# type: ignore
	_connected: bool = False

	@property
	def ext_offset(self) -> int:
		'''
		External offset: time to wait after trigger before the glitch voltage is applied after
		the trigger signal is received (in us)
		'''
		if self._ext_offset is None:
			# TODO get from device
			pass
		return self._ext_offset
	@ext_offset.setter
	def ext_offset(self, value: int):
		if self._ext_offset == value:
			return
		self._ext_offset = value
		self.s.write(struct.pack('<BI', struct.unpack('B', P_CMD_SET_EXT_OFFST)[0], value))
		if self.s.read(1) != P_CMD_RETURN_OK:
			raise ValueError('Could not set external offset')

	@property
	def width(self) -> int:
		'''
		Width: duration of the glitch pulse (in us)
		'''
		if self._width is None:
			# TODO get from device
			pass
		return self._width
	@width.setter
	def width(self, value: int):
		if self._width == value:
			return
		self._width = value
		self.s.write(struct.pack('<BI', struct.unpack('B', P_CMD_SET_WIDTH)[0], value))
		if self.s.read(1) != P_CMD_RETURN_OK:
			raise ValueError('Could not set width')

	def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 1.0):
		self.s = serial.Serial(port, baudrate, timeout=timeout)

	def ping(self) -> bool:
		'''
		Ping picocoder
		'''
		self.s.write(P_CMD_PING)
		if self.s.read(1) == P_CMD_PONG:
			return True
		return False

	def glitch_mul(self, glitch_setting: Annotated[tuple[int], 2], expected: int) -> tuple[GlitchResult, int|bytes|None]:
		'''
		Perform a glitch on `mul` with the given settings
		'''

		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		[self.ext_offset, self.width] = [*glitch_setting]

		self.s.reset_input_buffer() # Clear any pending data, just in case
		self.s.write(P_CMD_ARM)

		data = self.s.read(1)
		if not data:
			raise ConnectionError('Could not connect to picocoder')

		if data == P_CMD_RESULT_RESET:
			return GlitchResult.RESET, None
		if data == P_CMD_RESULT_ALIVE:
			ret_data = self.s.read(4)
			if not ret_data:
				raise ConnectionError('Did not receive data from picocoder after P_CMD_RESULT_ALIVE')
			ret_val = struct.unpack("<I", ret_data)[0]
			if ret_val == expected:
				return GlitchResult.NORMAL, None
			else:
				return GlitchResult.SUCCESS, ret_val
		if data == P_CMD_RESULT_DEAD:
			# TODO reset target?
			return GlitchResult.DEAD, data
		if data in [P_CMD_RESULT_DEAD, P_CMD_RESULT_ZOMBIE, P_CMD_RESULT_DATA_TIMEOUT, P_CMD_RESULT_UNREACHABLE,
			  P_CMD_RESULT_UNCONNECTABLE, P_CMD_RESULT_UNTRIGGERED, P_CMD_RESULT_PMIC_FAIL]:
			# TODO reset target?
			return GlitchResult.BROKEN, data
		return GlitchResult.WEIRD, data
