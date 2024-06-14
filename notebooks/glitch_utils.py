import random
import struct
from enum import Enum
from itertools import product
import time
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

P_CMD_PING					= b'\x70'	# Ping picocoder
P_CMD_TARGET_PING			= b'\x71'	# Ping from picocoder to target
P_CMD_UART_ECHO				= b'\x75'	# Set picocoder in UART echo mode (need power cycle to exit)
P_CMD_ESTIMATE_OFFSET		= b'\x76'	# Estimate glitch offset (see fw code to know what this does)
P_CMD_UART_DEBUG_TOGGLE		= b'\x77'	# Toggle debug pin (GPIO 16) on UART RX
P_CMD_VOLT_TEST				= b'\x78'	# Start voltage reliability test

P_CMD_RESULT_RESET			= b'\x50'	# Target reset
P_CMD_RESULT_ALIVE			= b'\x51'	# Target alive (data will follow)
P_CMD_RESULT_DEAD			= b'\x52'	# Target dead
P_CMD_RESULT_ZOMBIE			= b'\x53'	# Target is nor alive nor it reset after glitch
P_CMD_RESULT_DATA_TIMEOUT	= b'\x54'	# Target timeout after glitch when sending data back (target is alive)
P_CMD_RESULT_UNREACHABLE	= b'\x55'	# Target unavailable when starting glitch: did not receive anything on the serial port
P_CMD_RESULT_UNCONNECTABLE	= b'\x56'	# Target unavailable when starting glitch: did not receive the expected connection command
P_CMD_RESULT_UNTRIGGERED	= b'\x57'	# No trigger received after connection was established
P_CMD_RESULT_PMIC_FAIL		= b'\x58'	# Could not send command to PMIC
RESULT_NAMES = {
	P_CMD_RESULT_RESET			: 'RESET',
	P_CMD_RESULT_ALIVE			: 'ALIVE',
	P_CMD_RESULT_DEAD			: 'DEAD',
	P_CMD_RESULT_ZOMBIE			: 'ZOMBIE',
	P_CMD_RESULT_DATA_TIMEOUT	: 'DATA TIMEOUT',
	P_CMD_RESULT_UNREACHABLE	: 'UNREACHABLE',
	P_CMD_RESULT_UNCONNECTABLE	: 'UNCONNECTABLE',
	P_CMD_RESULT_UNTRIGGERED	: 'UNTRIGGERED',
	P_CMD_RESULT_PMIC_FAIL		: 'PMIC FAIL',
}

P_CMD_RETURN_OK				= b'\x61'	# Command successful
P_CMD_RETURN_KO				= b'\x62'	# Command failed
P_CMD_PONG					= b'\x63'	# Response to ping

VOLT_TEST_MSG_COUNT			= 50		# Number of messages sent from the target during voltage test

class GlitchResult(str, Enum): # str is needed to allow the enum to be a dict key (for the legend)
	'''
	Glitch result (processed from raw picocoder return codes)
	'''
	RESET					= 'xr'	# Red		Cross
	NORMAL					= '1b'	# Blue		Y (rotated cross)
	WEIRD					= '<y'	# Yellow	Triangle pointing left (solid)
	SUCCESS					= 'og'	# Green		Circle (solid)
	BROKEN					= 'Dm'	# Magenta	Diamond (solid)
	DEAD					= 'sk'	# Black		Square (solid)

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
	_voltage: int = None	# type: ignore
	_connected: bool = False

	def __init__(self, glitcher_port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 1.0):
		self.s = serial.Serial(glitcher_port, baudrate, timeout=timeout)

	def __del__(self):
		if self.s is not None:
			self.s.close()

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
		self.s.reset_input_buffer()
		self.s.write(struct.pack('<BI', struct.unpack('B', P_CMD_SET_EXT_OFFST)[0], value))
		ret = self.s.read(1)
		if not ret:
			raise ConnectionError('Could not set external offset: no response')
		if ret != P_CMD_RETURN_OK:
			raise ValueError(f'Could not set external offset. Received: 0x{ret.hex()}')

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
		self.s.reset_input_buffer()
		self.s.write(struct.pack('<BI', struct.unpack('B', P_CMD_SET_WIDTH)[0], value))
		ret = self.s.read(1)
		if not ret:
			raise ConnectionError('Could not set width: no response')
		if ret != P_CMD_RETURN_OK:
			raise ValueError(f'Could not set width. Received: 0x{ret.hex()}')

	@property
	def target_voltage(self) -> int:
		'''
		Target glitch voltage (byte, as specified in TPS65094, Table 6-3)
		'''
		if self._voltage is None:
			# TODO get from device
			raise NotImplementedError
		return self._voltage
	@target_voltage.setter
	def voltage(self, value: int):
		if self._voltage == value:
			return
		self._voltage = value
		self.s.reset_input_buffer()
		self.s.write(struct.pack('<BB', struct.unpack('B', P_CMD_SET_VOLTAGE)[0], value))
		ret = self.s.read(1)
		if not ret:
			raise ConnectionError('Could not set voltage: no response')
		if ret != P_CMD_RETURN_OK:
			reason = self.s.readline()
			raise ValueError(f'Could not set voltage. Received: 0x{ret.hex()}: {reason.decode('utf-8', errors='replace')}')

	@property
	def prep_voltage(self) -> int:
		'''
		Preparation voltage Vp - see Voltpillager paper
		'''
		raise NotImplementedError
		# TODO
	@prep_voltage.setter
	def prep_voltage(self, value: int):
		raise NotImplementedError
		# TODO

	@property
	def prept_time(self) -> int:
		'''
		Preparation time Tp (duration of the preparation voltage) in us - see Voltpillager paper
		'''
		# TODO
		raise NotImplementedError
	@prept_time.setter
	def prept_time(self, value: int):
		# TODO
		raise NotImplementedError

	def clear(self) -> None:
		'''
		Clear cached properties
		'''
		self._ext_offset = None	# type: ignore
		self._width = None		# type: ignore
		self._voltage = None	# type: ignore

	def ping(self) -> bool:
		'''
		Ping picocoder
		'''
		self.s.write(P_CMD_PING)
		if self.s.read(1) == P_CMD_PONG:
			return True
		return False

	def ping_target(self, timeout=1.5) -> bool:
		'''
		Ping target from picocoder

		Parameters:
			timeout: timeout in seconds (default = 1.5 - on average it takes 800ms for the target to boot)
		'''
		steps = int(timeout / 0.1) if timeout > 0.1 else 1
		old_timeout = self.s.timeout
		self.s.timeout = 0.01
		ret: bool = False

		self.s.reset_input_buffer()
		for _ in range(steps):
			self.s.write(P_CMD_TARGET_PING)
			res = self.s.read(1)
			if int.from_bytes(res, 'little'):
				ret = True
				break
			time.sleep(0.1)

		self.s.timeout = old_timeout
		return ret

	def find_crash_voltage(self, glitch_setting: Annotated[tuple[int], 2], expected: int) -> tuple[GlitchResult, int|bytes|None]:
		'''
		Estimates a stable voltage for the target

		Args:
			glitch_setting: Glitch settings to use. Tuple of (width, voltage)
			expected: Number of expected bytes sent by the target
		'''
		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		[self.width, self.voltage] = [*glitch_setting]

		self.s.reset_input_buffer() # Clear any pending data, just in case
		self.s.write(P_CMD_VOLT_TEST)

		data = self.s.read(4)
		if not data:
			raise ConnectionError('Did not get any data from picocoder after P_CMD_VOLT_TEST')

		result = struct.unpack("<i", data)[0]
		if result == expected:
			return GlitchResult.NORMAL, None
		elif result < expected and result > 0:
			return GlitchResult.WEIRD, result
		elif result == -1: # Unreachable
			return GlitchResult.DEAD, None
		elif result == -2: # No "ready"
			return GlitchResult.RESET, None
		elif result == -3: # Can't write PMIC
			return GlitchResult.BROKEN, None
		else:
			return GlitchResult.BROKEN, result

	def glitch_mul(self, glitch_setting: Annotated[tuple[int], 3], expected: int) -> tuple[GlitchResult, int|bytes|None]:
		'''
		Perform a glitch on `mul` with the given settings
		'''

		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		[self.ext_offset, self.width, self.voltage] = [*glitch_setting]

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
