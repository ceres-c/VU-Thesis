import struct

import glitch_utils
from glitch_utils import GlitchResult, GlitchyMcGlitchFace
from power_supply import PowerSupply, KA3305P

POWERSUPPLY_PORT = '/dev/ttyACM0'
GLITCHER_PORT = '/dev/ttyACM1'
GLITCHER_BAUD = 115200

def reset_target(ps: PowerSupply, glitcher: GlitchyMcGlitchFace, timeout: float = 1.5) -> bool:
	ps.power_cycle()
	return glitcher.ping_target(timeout)

ps = KA3305P(port=POWERSUPPLY_PORT)
ps.con()

glitcher = glitch_utils.GlitchyMcGlitchFace(GLITCHER_PORT, GLITCHER_BAUD)
gc = glitch_utils.GlitchController(groups=[r.name for r in GlitchResult], parameters=['ext_offset', 'width', 'voltage'])

glitcher.ext_offset = 500
glitcher.width = 5
glitcher.voltage = 0b0110011 # 1V
glitcher.s.reset_input_buffer() # Clear any pending data, just in case
glitcher.s.write(glitch_utils.P_CMD_VOLT_TEST)

read_result = glitcher.s.read(4)
read_result = struct.unpack("<i", read_result)[0]
print(f"Voltage test result: {read_result}")
'''
 -1: target is unreachable
 -2: could not send command to PMIC to set glitch target voltage/restore standard voltage
'''
if not glitcher.ping_target(timeout=0):
	reset_target(ps, glitcher)

glitcher.s.close()
