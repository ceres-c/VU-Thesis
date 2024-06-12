import struct

import glitch_utils
from glitch_utils import GlitchResult

PORT = '/dev/ttyACM1'
BAUD = 115200

glitcher = glitch_utils.GlitchyMcGlitchFace(PORT, BAUD)
gc = glitch_utils.GlitchController(groups=[r.name for r in GlitchResult], parameters=['ext_offset', 'width', 'voltage'])

glitcher.voltage = 0b0111101 # 1.1V
# glitcher.voltage = 0b0110011 # 1V
glitcher.s.reset_input_buffer() # Clear any pending data, just in case
glitcher.s.write(glitch_utils.P_CMD_VOLT_TEST)

read_result = glitcher.s.read(4)
read_result = struct.unpack("<i", read_result)[0]
print(f"Voltage test result: {read_result}")
'''
 -1: target is unreachable
 -2: could not send command to PMIC to set glitch target voltage
 -3: could not send command to PMIC to restore standard voltage
'''
glitcher.s.close()
