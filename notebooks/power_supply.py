import serial
import time

class PowerSupply:
	'''
	Base class for power supply controllers
	'''

	def __init__(self, cycle_wait: float = 0.3):
		'''
		Parameters:
			cycle_wait: power off -> power on delay on power cycle (seconds)
		'''
		self.cycle_wait = cycle_wait

	def __del__(self):
		self.dis()

	def con(self):
		'''
		Connect to the power supply
		'''
		raise NotImplementedError('Do not use the base class')

	def dis(self):
		'''
		Disconnect from the power supply
		'''
		raise NotImplementedError('Do not use the base class')

	@property
	def on(self) -> bool:
		'''
		Current power supply state
		'''
		raise NotImplementedError('Do not use the base class')
	@on.setter
	def on(self, value: bool):
		'''
		Turn on/off the power supply
		'''
		raise NotImplementedError('Do not use the base class')

	def power_cycle(self):
		'''
		Reset the power supply (blocking)
		'''
		self.on = False
		time.sleep(self.cycle_wait)
		self.on = True

class KA3305P(PowerSupply):
	'''
	KA3305P dual-channel power supply controller
	Information from KA3000-Series User Manual
	https://static.eleshop.nl/mage/media/wysiwyg/downloads/korad/ka3305_user_manual(1).pdf
	'''

	def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 9600, timeout: float = 1.0, cycle_wait: float = 0.3):
		'''
		Parameters:
			port: serial port to connect to
			baudrate: baudrate to use
			timeout: timeout for serial communication
			cycle_wait: power off -> power on delay on power cycle (seconds)
		'''
		super().__init__()
		self.port = port
		self.baudrate = baudrate
		self.timeout = timeout
		self.cycle_wait = cycle_wait
		self.s: serial.Serial = None # type: ignore

	def con(self):
		self.s = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
		self.s.write(b'*IDN?\r\n')
		idn = self.s.readline()
		if b'KORAD' not in idn:
			raise OSError('Not a KORAD power supply')

	def dis(self):
		if self.s:
			self.s.close()

	@property
	def on(self) -> bool:
		if not self.s:
			raise OSError('Not connected')
		self.s.write(b'STATUS?\r\n')
		status = self.s.read(1)
		return bool(status[0] & 0b1000000)
	@on.setter
	def on(self, value: bool):
		if not self.s:
			raise OSError('Not connected')
		self.s.write(b'OUT%d\r\n' % (1 if value else 0))
