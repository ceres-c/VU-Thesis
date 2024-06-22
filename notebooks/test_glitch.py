POWERSUPPLY_PORT = '/dev/ttyACM0'
GLITCHER_PORT = '/dev/ttyACM1'
GLITCHER_BAUD = 115200

import glitch_utils
from glitch_utils import GlitchyMcGlitchFace, GlitchResult
from power_supply import PowerSupply, KA3305P
import time

glitcher = glitch_utils.GlitchyMcGlitchFace(GLITCHER_PORT, GLITCHER_BAUD)
if not glitcher.ping():
	raise Exception("Glitcher not responding")

# ps = KA3305P(POWERSUPPLY_PORT)
# ps.con()
# ps.power_cycle()
ping = glitcher.ping_target()
print(f"Target is {'alive' if ping else 'dead'}")
exit(55)

gc = glitch_utils.GlitchController(groups=[r.name for r in GlitchResult], parameters=['ext_offset', 'width', 'voltage'])
gc.set_range('ext_offset', 1, 10)
gc.set_range('width', 1, 10)
gc.set_range('voltage', 0b0110011, 0b1001011) # 1V-1.24V - See Table 6-3 in TPS65094 datasheet

def reset_target(ps: PowerSupply, glitcher: GlitchyMcGlitchFace, timeout: float = 1.5) -> None:
	ps.power_cycle()
	if not glitcher.ping_target(timeout):
		raise Exception("Target not responding after reset")
	
for glitch_setting in gc.rand_glitch_values():
	try:
		read_result, read_data = glitcher.glitch_mul(glitch_setting)
		gc.add_result(glitch_setting, read_result)
		if read_result == GlitchResult.SUCCESS:
			[performed, result_a, result_b] = read_data
			print(f'SUCCESS! With {performed} iterations, {result_a} != {result_b}')
		if read_result == GlitchResult.WEIRD:
			print(f'Got weird response: 0x{read_data.hex()}')
		if read_result == GlitchResult.BROKEN:
			print(f'The target is in broken state: {glitch_utils.RESULT_NAMES[read_data]} (0x{int.from_bytes(read_data):x})')

		break
	except KeyboardInterrupt:
		break # Gentle stop, otherwise the plot might look empty