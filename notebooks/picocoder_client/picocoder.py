from enum import Enum
from math import ceil
import random
import struct
import time
from typing import Iterator, TypedDict

import matplotlib
import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import serial

from . import Target, TargetType

class GlitchSettings(TypedDict):
	'''
	Glitch settings
	'''
	ext_offset: int
	width: int
	voltage: int
	prep_voltage: int

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


P_CMD_ARM					= b'\x20'	# Arm glitch handler

P_CMD_FORCE					= b'\x30'	# Force write to PMBus to perform a glitch
P_CMD_SET_VOLTAGE			= b'\x31'	# Set glitch voltage
P_CMD_SET_EXT_OFFST			= b'\x32'	# Set external offset (wait after trig.) in us
P_CMD_SET_WIDTH				= b'\x33'	# Set glitch width	(duration of glitch) in us
P_CMD_SET_PREP_VOLTAGE		= b'\x34'	# Set Vp (preparation voltage) before glitch

P_CMD_PING					= b'\x70'	# Ping from host to picocoder
P_CMD_TARGET_PING			= b'\x71'	# Ping from picocoder to target
P_CMD_TARGET_PING_SLOW		= b'\x72'	# Ping from picocoder to target for slow targets (e.g. ucode update)
P_CMD_UART_ECHO				= b'\x75'	# Echo UART data from target to USB
P_CMD_MEASURE_LOOP_DURATION	= b'\x76'	# Measure the length (in us) of opcode loop
P_CMD_UART_TOGGLE_DEBUG_PIN	= b'\x77'	# Toggle debug pin on UART data in
P_CMD_DEBUG_PULSE			= b'\x78'	# Single 10 us pulse on debug pin

P_CMD_RESULT_RESET			= b'\x50'	# Target reset
P_CMD_RESULT_ALIVE			= b'\x51'	# Target is alive
P_CMD_RESULT_ZOMBIE			= b'\x52'	# Target is nor alive nor it reset after glitch
P_CMD_RESULT_DATA_TIMEOUT	= b'\x53'	# Target timeout after glitch when sending data back (target is alive)
P_CMD_RESULT_UNREACHABLE	= b'\x54'	# Target unavailable when starting glitch: did not receive anything on the serial port
P_CMD_RESULT_PMIC_FAIL		= b'\x55'	# Could not send command to PMIC
P_CMD_RESULT_ANSI_CTRL_CODE	= b'\x56'	# Target sent an ANSI control code, data will follow
RESULT_NAMES = {
	P_CMD_RESULT_RESET			: 'RESET',
	P_CMD_RESULT_ALIVE			: 'ALIVE',
	P_CMD_RESULT_ZOMBIE			: 'ZOMBIE',
	P_CMD_RESULT_DATA_TIMEOUT	: 'DATA TIMEOUT',
	P_CMD_RESULT_UNREACHABLE	: 'UNREACHABLE',
	P_CMD_RESULT_PMIC_FAIL		: 'PMIC FAIL',
	P_CMD_RESULT_ANSI_CTRL_CODE	: 'ANSI CTRL CODE',
}

P_CMD_RETURN_OK				= b'\x61'	# Command successful
P_CMD_RETURN_KO				= b'\x62'	# Command failed
P_CMD_PONG					= b'\x63'	# Response to ping

class GlitchController:
	'''
	Glitch campaign controller. Generates glitch values and stores results
	'''
	def __init__(self, groups: list[str], parameters: list[str], nominal_voltage: float):
		'''
		Args:
			groups: List of result groups (the possible result values)
			parameters: List of parameters that the glitch controller will generate (the glitch search space)
			nominal_voltage: Nominal voltage of the target (in V)
		'''
		self.groups = groups
		self.params = {param: {'start': 0, 'end': 0, 'step': 1} for param in parameters}
		self.nominal_voltage = nominal_voltage
		self.results: list[tuple[GlitchSettings, GlitchResult, tuple|bytes|None]] = []
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
		Generates an infinite sequence of random glitch values (repetitions are possible).

		It also checks if the current settings can achieve the required voltage drops and raises
		an error if they cannot.
		'''
		can_prep_voltage = self.check_prep_voltage()
		can_voltage = self.check_voltage()
		if not all([can_prep_voltage, can_voltage]):
			raise ValueError('The current settings cannot achieve the required voltage drops')

		while True:
			ret: GlitchSettings = {} # type: ignore
			for param in self.params:
				values = self.params[param]
				ret[param] = random.randrange(values['start'], values['end'] + 1, values['step'])
			yield ret

	def add_result(self, glitch_values: GlitchSettings, result: GlitchResult, data: tuple|bytes|None = None):
		'''
		Add a result to the result list, and update the plot if it is displayed

		Args:
			glitch_values: The glitch values used to achieve the result
			result: The result of the glitch
			data: Additional data returned by the glitcher (default: None)
		'''
		self.results.append((glitch_values, result, data))

		if self.ax and self.fig:
			self.ax.plot(glitch_values[self.xparam], glitch_values[self.yparam], result)
			self.fig.canvas.draw() # Guarantees live update of the plot whenever a new point is added

	def check_prep_voltage(self) -> bool:
		'''
		Checks if the configured preparation voltage range can be achieved with the
		configured external offset.
		Will print warnings if values are out of range

		Returns:
		False if the maximum required preparation voltage cannot be reached within the maximum ext_offset
		'''
		raise NotImplementedError('Use PMIC-specific glitch controller')

	def check_voltage(self) -> bool:
		'''
		Checks if the voltage is too small to achieve the required voltage drop with the
		configured width.
		Will print warnings if values are out of range.

		Returns:
		False if the maximum required voltage cannot be reached within the maximum width
		'''
		raise NotImplementedError('Use PMIC-specific glitch controller')

	def check_settings(self, gs: GlitchSettings) -> bool:
		'''
		Checks if some specific settings can achieve the required voltage drops, both
		Vcc -> Vp and Vp -> Vf

		Args:
			gs: Glitch settings
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
		for glitch_values, result, _ in self.results:
			ax.plot(glitch_values[xparam], glitch_values[yparam], result)
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
		for glitch_values, result, _ in self.results:
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

	def check_prep_voltage(self) -> bool:
		# Convert VID to millivolts
		prep_voltage_min = min(self.params['prep_voltage']['start'], self.params['prep_voltage']['end'])
		prep_voltage_min_mv = 0 if prep_voltage_min == 0 else 500 + (prep_voltage_min - 1) * 10

		ext_offset_min = min(self.params['ext_offset']['start'], self.params['ext_offset']['end'])
		ext_offset_max = max(self.params['ext_offset']['start'], self.params['ext_offset']['end'])

		max_delta_prep_voltage = abs(prep_voltage_min_mv - self.nominal_voltage * 1000)
		required_time_voltage_prep = ceil(max_delta_prep_voltage / self.SLEW_RATE - 2*self.I2C_CMD_TRANSMIT) # Time in integer us

		can_prep_min = required_time_voltage_prep <= ext_offset_min
		can_prep_max = required_time_voltage_prep <= ext_offset_max
		if not can_prep_max:
			print(f'Warning: The minimum target of Vp={prep_voltage_min_mv}mV (delta {max_delta_prep_voltage}mV) cannot be achieved within the maximum ext_offset={ext_offset_max}us. Required ext_offset >= {required_time_voltage_prep}us')
		elif not can_prep_min:
			print(f'Warning: The minimum target of Vp={prep_voltage_min_mv}mV (delta {max_delta_prep_voltage}mV) cannot be achieved within the minimum ext_offset={ext_offset_min}us. Required ext_offset >= {required_time_voltage_prep}us')
		return can_prep_max

	def check_voltage(self) -> bool:
		# Convert VID to voltage
		voltage_min = min(self.params['voltage']['start'], self.params['voltage']['end'])
		voltage_min_mv = 0 if voltage_min == 0 else 500 + (voltage_min - 1) * 10
		prep_voltage_max = max(self.params['prep_voltage']['start'], self.params['prep_voltage']['end'])
		prep_voltage_max_mv = 0 if prep_voltage_max == 0 else 500 + (prep_voltage_max - 1) * 10

		width_min = min(self.params['width']['start'], self.params['width']['end'])
		width_max = max(self.params['width']['start'], self.params['width']['end'])

		max_delta_voltage = abs(voltage_min_mv - prep_voltage_max_mv)
		required_time_voltage = ceil(max_delta_voltage / self.SLEW_RATE - 2*self.I2C_CMD_TRANSMIT) # Time in integer us

		can_voltage_min = required_time_voltage <= width_min
		can_voltage_max = required_time_voltage <= width_max
		if not can_voltage_max:
			print(f'Warning: The minimum target of Vf={voltage_min_mv}mV (delta {max_delta_voltage}mV) cannot be achieved within the maximum width={width_max}us. Required width >= {required_time_voltage}us')
		elif not can_voltage_min:
			print(f'Warning: The minimum target of Vf={voltage_min_mv}mV (delta {max_delta_voltage}mV) cannot be achieved within the minimum width={width_min}us. Required width >= {required_time_voltage}us')
		return can_voltage_max

	def check_settings(self, gs: GlitchSettings) -> bool:
		# Convert VID to voltage
		prep_voltage_v = 0 if gs['prep_voltage'] == 0 else 0.5 + (gs['prep_voltage'] - 1) * 0.01
		voltage_v = 0 if gs['voltage'] == 0 else 0.5 + (gs['voltage'] - 1) * 0.01

		delta_t_prep = self.I2C_CMD_TRANSMIT + gs['ext_offset']
		max_voltage_drop_prep = delta_t_prep * self.SLEW_RATE / 1000
		delta_v_prep = abs(self.nominal_voltage - prep_voltage_v)

		delta_t_glitch = self.I2C_CMD_TRANSMIT + gs['width']
		max_voltage_drop_glitch = delta_t_glitch * self.SLEW_RATE / 1000
		delta_v_glitch = abs(prep_voltage_v - voltage_v)

		return max_voltage_drop_prep > delta_v_prep and max_voltage_drop_glitch > delta_v_glitch


class Picocoder:
	'''
	Interface with firmware running on the glitcher
	'''

	s: serial.Serial = None # type: ignore

	tc: TargetType = Target()

	# Locally cached properties
	_ext_offset: int = None # type: ignore
	_width: int = None		# type: ignore
	_voltage: int = None	# type: ignore
	_prep_voltage: int = None # type: ignore
	_connected: bool = False

	def __init__(self, glitcher_port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 1.0):
		'''
		Initialize the glitcher interface

		Args:
			target_class (str): The class of code running on the target, see :py:attr:`~target_types`
			glitcher_port (str, optional): The port for the glitcher device. Defaults to '/dev/ttyACM0'.
			baudrate (int, optional): The baudrate for serial communication. Defaults to 115200.
			timeout (float, optional): The timeout value for serial communication. Defaults to 1.0.
			slow_target (bool, optional): If True, the target is slow and requires a longer ping timeout. Defaults to False.
		'''
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
			raise ValueError(f'Could not set voltage. Received: 0x{ret.hex()}: {reason.decode("utf-8", errors="replace")}')

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

		NOTE: Right after boot the target CPU is slower than usual, so waiting for the target to perform some
			  iterations of the loop before considering it alive is a good idea (implemented in firmware code)

		Args:
			n: number of attempts to ping the target
			delay: delay between attempts
		'''
		old_timeout = self.s.timeout
		self.s.timeout = 0.5 # This function might take some extra time on the pico side (wait for vcore to reach setpoint)
		ret: bool = False

		if not issubclass(type(self.tc) , Target):
			raise ValueError('Set target type before trying to ping it')

		for _ in range(n):
			self.s.reset_input_buffer()
			self.s.write(P_CMD_TARGET_PING if not self.tc.is_slow else P_CMD_TARGET_PING_SLOW)
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
		old_timeout = self.s.timeout	# This function might take a lot of time on the pico side,
										# as it waits for the target to perform some iterations of the loop
		self.s.timeout = 2
		self.s.reset_input_buffer()
		self.s.write(P_CMD_MEASURE_LOOP_DURATION)
		data = self.s.read(4)
		self.s.timeout = old_timeout
		if not data:
			raise ConnectionError('Did not get any data from picocoder after P_CMD_MEASURE_LOOP_DURATION')
		return struct.unpack('<i', data)[0]

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

	def glitch(self, glitch_setting: GlitchSettings) -> tuple[GlitchResult, tuple|bytes|None]:
		'''
		Perform a glitch with the given settings against the target class :py:attr:`~clss`.

		Args:
			glitch_setting: Settings for this attempt
			filt: A function that takes the data returned by the target after the glitch and returns True if the glitch was successful

		Returns:
			The second item in the returned tuple is the data returned by the target after the glitch,
			be it:
				- TODO
		'''
		if not self._connected:
			ping = self.ping()
			if not ping:
				raise ConnectionError('Could not connect to picocoder')
			self._connected = ping

		self._apply_settings(glitch_setting)

		self.s.reset_input_buffer() # Clear any pending data, just in case
		self.s.write(P_CMD_ARM)
		if self.tc.ret_count > 255:
			raise ValueError('Too many return values')
		self.s.write(self.tc.ret_count.to_bytes(1, 'little'))

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
		elif data == P_CMD_RESULT_ALIVE:
			# Target is alive
			retlist = []
			for retval in self.tc.ret_vars:
				data = self.s.read(4)
				if not data:
					raise ConnectionError(f'Did not receive expected value {retval} from picocoder after P_CMD_RESULT_ALIVE')
				retlist.append(struct.unpack('<I', data)[0])
			ret = tuple(retlist)
			if self.tc.is_success(ret):
				return GlitchResult.SUCCESS, ret
			else:
				return GlitchResult.NORMAL, ret
		elif data == P_CMD_RESULT_DATA_TIMEOUT:
			# Target is alive, but it did not send (all) expected data back after glitch
			return GlitchResult.WEIRD, None
		elif data == P_CMD_RESULT_ZOMBIE:
			# Target sent some other unexpected data
			unexpected_data = self.s.read(1)
			if not unexpected_data:
				raise ConnectionError('Did not receive unexpected data from picocoder after P_CMD_RESULT_ZOMBIE')
			return GlitchResult.WEIRD, unexpected_data
		elif data == P_CMD_RESULT_ANSI_CTRL_CODE:
			ret_data = b''
			# Target sent an ANSI control code, data will follow
			# Set shorter timeout and read one byte at a time
			time.sleep(2) # HACK Wait for pico to retrieve data from target
			timeout_old = self.s.timeout
			self.s.timeout = 0.2
			while True:
				read_data = self.s.read(1)
				if not read_data:
					break
				ret_data += read_data
			self.s.timeout = timeout_old
			return GlitchResult.WEIRD, ret_data
		else:
			return GlitchResult.WEIRD, data
