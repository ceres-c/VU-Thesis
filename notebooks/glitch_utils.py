from enum import Enum
from itertools import product
from typing import Annotated, Optional
import random
import struct

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
P_CMD_RESULT_WEIRD			= b'\x52'	# Target weird
P_CMD_RESULT_DATA_TIMEOUT	= b'\x53'	# Target timeout (e.g. target already sent post-glitch data)

P_CMD_RETURN_OK				= b'\x61'	# Command successful
P_CMD_RETURN_KO				= b'\x62'	# Command failed

class GlitchResult(Enum):
	TIMEOUT		= 0
	TIMEOUT2	= 1
	RESET		= 2
	NORMAL		= 3
	WEIRD		= 4
	SUCCESS		= 5

def result_to_plt(result: GlitchResult) -> str:
	'''
	Convert a GlitchResult to a matplotlib-compatible scatter plot marker
	'''
	dic = {
		GlitchResult.SUCCESS: 'og',
		GlitchResult.RESET: 'xr',
		GlitchResult.NORMAL: 'yb',
		GlitchResult.WEIRD: '<y',
		GlitchResult.TIMEOUT: '^r',
		GlitchResult.TIMEOUT2: '^c',
	}
	return dic[result]

class GlitchController:
	def __init__(self, groups: list[str], parameters: list[str]):
		self.groups = groups
		self.params = {param: {'start': 0, 'end': 0, 'step': 1} for param in parameters}

	def set_range(self, param: str, start: int, end: int) -> None:
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['start'] = start
		self.params[param]['end'] = end

	def set_step(self, param: str, step: int) -> None:
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['step'] = step

	def rand_glitch_values(self) -> tuple[int, ...]: # type: ignore
		ranges = [list(range(param['start'], param['end'] + 1, param['step'])) for param in self.params.values()]
		for r in ranges:
			random.shuffle(r)
		yield from product(*ranges) # type: ignore

class GlitchyMcGlitchFace:
	s: serial.Serial = None # type: ignore

	# Locally cached properties
	_ext_offset: int = None # type: ignore
	_width: int = None		# type: ignore

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

	def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 1.0):
		self.s = serial.Serial(port, baudrate, timeout=timeout)

	def glitch_mul(self, glitch_setting: Annotated[tuple[int], 2], expected: int) -> tuple[GlitchResult, Optional[int]]:
		'''
		Perform a glitch on `mul` with the given settings
		'''

		[self.ext_offset, self.width] = [*glitch_setting]

		self.s.write(P_CMD_ARM)

		data = self.s.read(1)
		if not data:
			return GlitchResult.TIMEOUT, None
		if data == P_CMD_RESULT_RESET:
			return GlitchResult.RESET, None
		if data == P_CMD_RESULT_ALIVE:
			ret_data = self.s.read(4)
			if not ret_data:
				return GlitchResult.TIMEOUT2, None
			ret_val = struct.unpack("<I", ret_data)[0]
			if ret_val == expected:
				return GlitchResult.NORMAL, None
			else:
				return GlitchResult.SUCCESS, ret_val
		if data == P_CMD_RESULT_WEIRD:
			return GlitchResult.WEIRD, None
		if data == P_CMD_RESULT_DATA_TIMEOUT:
			return GlitchResult.TIMEOUT, None
		return GlitchResult.WEIRD, None