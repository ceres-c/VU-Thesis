import random
import struct
import time
import matplotlib
import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot as plt
from enum import Enum
from matplotlib.ticker import MaxNLocator
from typing import Annotated, Iterator, TypedDict

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
P_CMD_SET_PREP_VOLTAGE		= b'\x26'	# Set Vp (preparation voltage) before glitch
P_CMD_SET_PREP_TIME			= b'\x27'	# Set Tp (preparation width) before glitch

P_CMD_PING					= b'\x70'	# Ping from host to picocoder
P_CMD_TARGET_PING			= b'\x71'	# Ping from picocoder to target
P_CMD_UART_ECHO				= b'\x75'	# Echo UART data from target to USB
P_CMD_MEASURE_LOOP_DURATION	= b'\x76'	# Measure the length (in us) of opcode loop
P_CMD_UART_TOGGLE_DEBUG_PIN	= b'\x77'	# Toggle debug pin on UART data in
P_CMD_DEBUG_PULSE			= b'\x78'	# Single 10 us pulse on debug pin

P_CMD_RESULT_RESET			= b'\x50'	# Target reset
P_CMD_RESULT_NORMAL			= b'\x51'	# No glitch achieved
P_CMD_RESULT_SUCCESS		= b'\x52'	# Glitched successfully
P_CMD_RESULT_ZOMBIE			= b'\x53'	# Target is nor alive nor it reset after glitch
P_CMD_RESULT_DATA_TIMEOUT	= b'\x54'	# Target timeout after glitch when sending data back (target is alive)
P_CMD_RESULT_UNREACHABLE	= b'\x55'	# Target unavailable when starting glitch: did not receive anything on the serial port
P_CMD_RESULT_PMIC_FAIL		= b'\x56'	# Could not send command to PMIC
RESULT_NAMES = {
	P_CMD_RESULT_RESET			: 'RESET',
	P_CMD_RESULT_NORMAL			: 'NORMAL',
	P_CMD_RESULT_SUCCESS		: 'SUCCESS',
	P_CMD_RESULT_ZOMBIE			: 'ZOMBIE',
	P_CMD_RESULT_DATA_TIMEOUT	: 'DATA TIMEOUT',
	P_CMD_RESULT_UNREACHABLE	: 'UNREACHABLE',
	P_CMD_RESULT_PMIC_FAIL		: 'PMIC FAIL',
}

P_CMD_RETURN_OK				= b'\x61'	# Command successful
P_CMD_RETURN_KO				= b'\x62'	# Command failed
P_CMD_PONG					= b'\x63'	# Response to ping

VOLT_TEST_MSG_COUNT			= 50		# Number of messages sent from the target during voltage test

class GlitchResult(str, Enum):
	'''
	Glitch result (processed from raw picocoder return codes)
	We have multiple colors and shapes here to give a fine-grained view of the results,
	this can prove to be overwhelming with thousands of points on the plot, so it can
	be advisable to merge some of the results into a single color/shape.
	'''
	RESET					= 'xr'	# Red		X
	NORMAL					= '1b'	# Blue		Y (rotated cross)
	WEIRD					= '<y'	# Yellow	Triangle pointing left (solid)
	SUCCESS					= 'og'	# Green		Circle (solid)
	HALF_SUCCESS			= '^c'	# Cyan		Triangle pointing up (solid)
	BROKEN					= 'Xm'	# Magenta	X (filled)

class GlitchSettings(TypedDict):
	'''
	Glitch settings
	'''
	ext_offset: int
	width: int
	voltage: int
	prep_voltage: int

class GlitchController:
	'''
	Glitch campaign controller. Generates glitch values and stores results
	'''
	def __init__(self, groups: list[str], parameters: list[str]):
		'''
		Args:
			groups: List of result groups (the possible result values)
			parameters: List of parameters that the glitch controller will generate (the glitch search space)
		'''
		self.groups = groups
		self.params = {param: {'start': 0, 'end': 0, 'step': 1} for param in parameters}
		self.results: list[tuple[GlitchSettings, GlitchResult]] = []
		self.fig: matplotlib.figure.Figure = None # type: ignore
		self.ax: matplotlib.axes.Axes = None # type: ignore
		self.xparam: str = None # type: ignore
		self.yparam: str = None # type: ignore

	def set_range(self, param: str, start: int, end: int) -> None:
		'''
		Set the range of a parameter

		Args:
			param: Name of the parameter to set
			start: Start value
			end: End value
		'''
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['start'] = start
		self.params[param]['end'] = end

	def set_step(self, param: str, step: int) -> None:
		'''
		Set the stepping value of a parameter (how much to increment/decrement the parameter by)

		Args:
			param: Name of the parameter to set
			step: Step value
		'''
		if param not in self.params:
			raise ValueError(f'Parameter {param} not found')
		self.params[param]['step'] = step

	def rand_glitch_values(self) -> Iterator[GlitchSettings]:
		'''
		Generates an infinite sequence of random glitch values (repetitions are possible)
		'''
		while True:
			ret: GlitchSettings = {} # type: ignore
			for param in self.params:
				values = self.params[param]
				ret[param] = random.randrange(values['start'], values['end'] + 1, values['step'])
			yield ret

	def add_result(self, glitch_values: GlitchSettings, result: GlitchResult):
		'''
		Add a result to the result list, and update the plot if it is displayed

		Args:
			glitch_values: The glitch values used to achieve the result
			result: The result of the glitch
		'''
		self.results.append((glitch_values, result))

		if self.ax and self.fig:
			self.ax.plot(glitch_values[self.xparam], glitch_values[self.yparam], result, s=10)
			self.fig.canvas.draw() # Guarantees live update of the plot whenever a new point is added

	def check_width(self, width: int, prep_voltage: int, voltage: int):
		'''
		Checks if the width is too small to achieve the required voltage drop

		Args:
			width: The width to check in us
			prep_voltage: The prep voltage VID (Voltage IDentifier) from PMIC datasheet
			voltage: The voltage drop VID
		'''
		raise NotImplementedError('Use PMIC-specific glitch controller')

	def draw_graph(self, xparam: str, yparam: str, integer_axis: bool = True):
		'''
		Draws a dynamic graph of the results
		NOTE If used in a jupyter notebook, the plot will be displayed live only if the figure
		is generated in a different cell than the one that adds data to the plot

		Args:
			xparam: The parameter to use as the x-axis
			yparam: The parameter to use as the y-axis
			integer_axis: If True, the axis ticks will be integer-only (default: True)
		'''
		if self.ax:
			self.ax.clear()
		if self.fig:
			self.fig.clear()
			plt.close(self.fig)
		self.fig, self.ax = plt.subplots()
		if integer_axis:
			self.ax.yaxis.set_major_locator(MaxNLocator(integer=True))
			self.ax.xaxis.set_major_locator(MaxNLocator(integer=True))
		if xparam not in self.params:
			raise ValueError(f'Parameter {xparam} not found')
		self.xparam = xparam
		if yparam not in self.params:
			raise ValueError(f'Parameter {yparam} not found')
		self.yparam = yparam

	def redraw_graph(self):
		'''
		Redraws the graph with the current results and x/y axes settings
		'''
		self.fig.canvas.draw()

	def draw_graph_view(self, xparam: str, yparam: str, integer_axis: bool = True) -> tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]:
		'''
		Draws another view (static) of the current results with the given x/y parameters.
		Graphs plotted with this function are not updated when new results are added.

		Args:
			xparam: The parameter to use as the x-axis
			yparam: The parameter to use as the y-axis
			integer_axis: If True, the axis ticks will be integer-only (default: True)
		'''

		fig, ax = plt.subplots()
		if integer_axis:
			ax.yaxis.set_major_locator(MaxNLocator(integer=True))
			ax.xaxis.set_major_locator(MaxNLocator(integer=True))
		if xparam not in self.params:
			raise ValueError(f'Parameter {xparam} not found')
		if yparam not in self.params:
			raise ValueError(f'Parameter {yparam} not found')
		for glitch_values, result in self.results:
			ax.plot(glitch_values[xparam], glitch_values[yparam], result, s=10)
		return fig, ax

	def draw_graph_view_filter(self, xparam: str, yparam: str, print_last: GlitchResult, integer_axis: bool = True):
		'''
		Draws another view (static) of the current results with the given x/y parameters.
		Results of type `print_last` are printed last to highlight them when overlapped with other results.
		Graphs plotted with this function are not updated when new results are added.

		Args:
			xparam: The parameter to use as the x-axis
			yparam: The parameter to use as the y-axis
			print_last: The result type to print last
			integer_axis: If True, the axis ticks will be integer-only (default: True)
		'''
		fig, ax = plt.subplots()
		if integer_axis:
			ax.yaxis.set_major_locator(MaxNLocator(integer=True))
			ax.xaxis.set_major_locator(MaxNLocator(integer=True))
		if xparam not in self.params:
			raise ValueError(f'Parameter {xparam} not found')
		if yparam not in self.params:
			raise ValueError(f'Parameter {yparam} not found')
		delayed = set()
		for glitch_values, result in self.results:
			if result == print_last:
				delayed.add((glitch_values, result))
			else:
				ax.plot(glitch_values[xparam], glitch_values[yparam], result)
		for glitch_values, result in delayed:
			ax.plot(glitch_values[xparam], glitch_values[yparam], result)
		return fig, ax

class GlitchControllerTPS65094(GlitchController):
	'''
	Glitch controller for TPS65094 PMIC on Up Squared Pentium N4200 boards
	'''
	I2C_CMD_TRANSMIT = 36 # us
	SLEW_RATE = 3 # mV/us

	def check_width(self, width: int, prep_voltage: int, voltage: int):
		# Convert VID to voltage
		voltage_v = 0 if voltage == 0 else 0.5 + (voltage - 1) * 0.01
		prep_voltage_v = 0 if prep_voltage == 0 else 0.5 + (prep_voltage - 1) * 0.01

		delta_t = self.I2C_CMD_TRANSMIT + width
		max_voltage_drop = delta_t * self.SLEW_RATE / 1000
		delta_v = abs(prep_voltage_v - voltage_v)
		return max_voltage_drop > delta_v

class Picocoder:
	'''
	Interface with the picocode glitcher firmware
	'''
	s: serial.Serial = None # type: ignore

	# Locally cached properties
	_ext_offset: int = None # type: ignore
	_width: int = None		# type: ignore
	_voltage: int = None	# type: ignore
	_prep_voltage: int = None # type: ignore
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
			raise NotImplementedError('No command to read this property from glitcher')
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
			raise NotImplementedError('No command to read this property from glitcher')
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
			raise NotImplementedError('No command to read this property from glitcher')
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
		if self._prep_voltage is None:
			# TODO get from device
			raise NotImplementedError('No command to read this property from glitcher')
		return self._prep_voltage
	@prep_voltage.setter
	def prep_voltage(self, value: int):
		if self._prep_voltage == value:
			return
		self._prep_voltage = value
		self.s.reset_input_buffer()
		self.s.write(struct.pack('<BB', struct.unpack('B', P_CMD_SET_PREP_VOLTAGE)[0], value))
		ret = self.s.read(1)
		if not ret:
			raise ConnectionError('Could not set preparation voltage: no response')
		if ret != P_CMD_RETURN_OK:
			raise ValueError(f'Could not set preparation voltage. Received: 0x{ret.hex()}')

	def _apply_settings(self, glitch_setting: GlitchSettings) -> None:
		for param, value in glitch_setting.items():
			try:
				getattr(self, param)
			# Will throw AttributeError (not caught) if the property does not exist
			except NotImplementedError:
				# This is expected behavior with some properties, they are set-only
				pass
			setattr(self, param, value)

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
		self.s.reset_input_buffer()
		self.s.write(P_CMD_PING)
		if self.s.read(1) == P_CMD_PONG:
			return True
		return False

	def ping_target(self, n = 15, delay = 0.1) -> bool:
		'''
		Ping target from picocoder.
		At the glitcher end, the target ping funciton either returns within 7ms if the target is dead, or
		after 350ms if the target is alive (gives VCore time to ramp up, in case the target just came up).
		Therefore, this function could possibly take a considerable amount of time (0.5s) to execute.

		Args:
			n: number of attempts to ping the target
			delay: delay between attempts
		'''
		old_timeout = self.s.timeout
		self.s.timeout = 0.5 # This function might take some extra time on the pico side (wait for vcore to reach setpoint)
		ret: bool = False

		for _ in range(n):
			self.s.reset_input_buffer()
			self.s.write(P_CMD_TARGET_PING)
			res = self.s.read(1)
			if int.from_bytes(res, 'little'):
				ret = True
				break
			time.sleep(delay)

		self.s.timeout = old_timeout
		return ret

	def measure_loop_duration(self) -> int:
		'''
		Asks the picocoder to measure the length (in us) of opcode loop, aka the time between two
		consecutive trigger signals.
		'''
		self.s.reset_input_buffer()
		self.s.write(P_CMD_MEASURE_LOOP_DURATION)
		data = self.s.read(4)
		if not data:
			raise ConnectionError('Did not get any data from picocoder after P_CMD_MEASURE_LOOP_DURATION')
		return struct.unpack("<i", data)[0]

	def uart_toggle_debug_pin(self) -> None:
		'''
		Toggle debug pin (GPIO 16) on UART RX
		This is used to measure the time between data appears on the channel and the pico detects it
		'''
		self.s.reset_input_buffer()
		self.s.write(P_CMD_UART_TOGGLE_DEBUG_PIN)
		data = self.s.read(1)
		if not data:
			raise ConnectionError('Could not toggle debug pin: no response')
		if not bool(data):
			raise ValueError(f'Could not toggle debug pin. Received: 0x{data.hex()}')

	def glitch_mul(self, glitch_setting: GlitchSettings) -> tuple[GlitchResult, tuple|bytes|None]:
		'''
		Perform a glitch on `mul` with the given settings.
		When a successful glitch is performed, the function returns a tuple with:
			- the number of performed iterations
			- result_a
			- result_b
		where result_a and result_b are the two multiplication values
		'''

		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		self._apply_settings(glitch_setting)

		self.s.reset_input_buffer() # Clear any pending data, just in case
		self.s.write(P_CMD_ARM)

		data = self.s.read(1)
		if not data:
			raise ConnectionError('Could not connect to picocoder')

		if data == P_CMD_RESULT_UNREACHABLE:
			# No trigger received
			return GlitchResult.BROKEN, data
		elif data == P_CMD_RESULT_PMIC_FAIL:
			# Could not send command to PMIC
			return GlitchResult.BROKEN, data
		elif data == P_CMD_RESULT_RESET:
			# Target died during the glitch
			return GlitchResult.RESET, None
		elif data == P_CMD_RESULT_NORMAL:
			# Glitch did not work, board continued running normally
			return GlitchResult.NORMAL, None
		elif data == P_CMD_RESULT_SUCCESS:
			# Glitch worked
			performed = self.s.read(4)
			if not performed:
				raise ConnectionError('Did not receive performed iterations count from picocoder after P_CMD_RESULT_SUCCESS')
			performed = struct.unpack("<I", performed)[0]
			result_a = self.s.read(4)
			if not result_a:
				raise ConnectionError('Did not receive result_a from picocoder after P_CMD_RESULT_SUCCESS')
			result_a = struct.unpack("<I", result_a)[0]
			result_b = self.s.read(4)
			if not result_b:
				raise ConnectionError('Did not receive result_b from picocoder after P_CMD_RESULT_SUCCESS')
			result_b = struct.unpack("<I", result_b)[0]
			return GlitchResult.SUCCESS, (performed, result_a, result_b)
		elif data == P_CMD_RESULT_DATA_TIMEOUT:
			# Target reported a success when glitching, but did not send data back after glitch
			return GlitchResult.HALF_SUCCESS, data
		elif data == P_CMD_RESULT_ZOMBIE:
			# Target sent some other unexpected data
			unexpected_data = self.s.read(1)
			if not unexpected_data:
				raise ConnectionError('Did not receive unexpected data from picocoder after P_CMD_RESULT_ZOMBIE')
			return GlitchResult.WEIRD, unexpected_data
		else:
			return GlitchResult.WEIRD, data


	def mul_test_vp(self, glitch_setting: Annotated[tuple[int], 2]) -> tuple[GlitchResult, tuple|bytes|None]:
		'''
		Perform a glitch on `mul` with the given settings.
		When a successful glitch is performed, the function returns a tuple with:
			- the number of successful glitches in the current loop
			- result_a
			- result_b
		where result_a and result_b are the two multiplication values

		Args:
			glitch_setting: Glitch settings to use. Tuple of (ext_offset, prep_voltage)
		'''

		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		[self.ext_offset, self.prep_voltage] = [*glitch_setting]

		self.s.reset_input_buffer() # Clear any pending data, just in case
		self.s.write(P_CMD_ARM)

		data = self.s.read(1)
		if not data:
			raise ConnectionError('Could not connect to picocoder')

		if data == P_CMD_RESULT_UNREACHABLE:
			# No trigger received
			return GlitchResult.BROKEN, data
		elif data == P_CMD_RESULT_PMIC_FAIL:
			# Could not send command to PMIC
			return GlitchResult.BROKEN, data
		elif data == P_CMD_RESULT_RESET:
			# Target died during the glitch
			return GlitchResult.RESET, None
		elif data == P_CMD_RESULT_NORMAL:
			# Glitch did not work, board continued running normally
			return GlitchResult.NORMAL, None
		elif data == P_CMD_RESULT_SUCCESS:
			# Glitch worked
			performed = self.s.read(4)
			if not performed:
				raise ConnectionError('Did not receive performed iterations count from picocoder after P_CMD_RESULT_SUCCESS')
			performed = struct.unpack("<I", performed)[0]
			result_a = self.s.read(4)
			if not result_a:
				raise ConnectionError('Did not receive result_a from picocoder after P_CMD_RESULT_SUCCESS')
			result_a = struct.unpack("<I", result_a)[0]
			result_b = self.s.read(4)
			if not result_b:
				raise ConnectionError('Did not receive result_b from picocoder after P_CMD_RESULT_SUCCESS')
			result_b = struct.unpack("<I", result_b)[0]
			return GlitchResult.SUCCESS, (performed, result_a, result_b)
		elif data == P_CMD_RESULT_DATA_TIMEOUT:
			# Target reported a success when glitching, but did not send data back after glitch
			return GlitchResult.HALF_SUCCESS, data
		elif data == P_CMD_RESULT_ZOMBIE:
			# Target sent some other unexpected data
			unexpected_data = self.s.read(1)
			if not unexpected_data:
				raise ConnectionError('Did not receive unexpected data from picocoder after P_CMD_RESULT_ZOMBIE')
			return GlitchResult.WEIRD, unexpected_data
		else:
			return GlitchResult.WEIRD, data
