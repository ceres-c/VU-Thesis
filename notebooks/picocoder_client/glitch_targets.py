'''
Container for all target code type-related information.
'''

from typing import TypeAlias

class Target:
	'''
	Represents the kind of code running on the target.
	'''

	op_name: str = 'unknown'
	ret_vars: list[str] = []
	is_slow: bool = False

	@property
	def ret_count(self) -> int:
		'''
		Number of return values.
		'''
		return len(self.ret_vars)

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		raise NotImplementedError

class TargetMul(Target):
	'''
	Target is running imuls.
	'''

	op_name = 'mul'
	ret_vars = ['fault_count']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(fault_count, ) = from_target
		return fault_count > 0

class TargetLoad(Target):
	'''
	Target is running loads.
	'''

	op_name = 'load'
	ret_vars = ['fault_count', 'wrong_value']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(fault_count, ) = from_target
		return fault_count > 0

class TargetCmp(Target):
	'''
	Target is running cmps.
	'''

	op_name = 'cmp'
	ret_vars = ['fault_count']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(fault_count, ) = from_target
		return fault_count > 0
	
class TargetReg(Target):
	'''
	Target is moving data between subregisters and adding up the destination register.
	'''

	op_name = 'reg'
	ret_vars = ['summation']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(summation, ) = from_target
		return summation != 271000 # We add 1 to rcx 271k times

class TargetRdrandSubAdd(Target):
	'''
	Target is running rdrand patched to perform
	`rcx += rax - rbx`
	'''

	op_name = 'rdrand-sub_add'
	ret_vars = ['fault_count']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(fault_count, ) = from_target
		return fault_count > 0

class TargetRdrandAdd(Target):
	'''
	Target is running rdrand patched to perform
	`rcx += 1`
	'''

	op_name = 'rdrand-add'
	ret_vars = ['summation']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(summation, ) = from_target
		return summation != 120000 # Number of rdrand calls

class TargetRdrandAddMany(Target):
	'''
	Target is running rdrand patched to perform
	`rcx += 10`
	'''

	op_name = 'rdrand-add_many'
	ret_vars = ['summation']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(summation, ) = from_target
		return summation != 900000 # 90k rdrand calls * 10

class TargetRdrandMovRegs(Target):
	'''
	Target is running rdrand patched to perform
	`rcx = rcx`
	After moving the source value of rcx around in temp registers
	'''

	op_name = 'rdrand-mov_regs'
	ret_vars = ['output']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(output, ) = from_target
		return output != 0xFFFFFFFF

class TargetRdrandLoopAdd(Target):
	'''
	Target is running rdrand patched to perform
	```
	for (i = 0; i < 0xDFFFF; i++)
		rcx += 1
		rcx += 1
		rcx += 1
	```
	'''

	op_name = 'rdrand-loop_add'
	ret_vars = ['summation']
	is_slow = True

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(summation, ) = from_target
		return summation != 0x29FFFD and summation < 0x52000000
		# 0x52 is `R` in ASCII, when the pi pico misinterprets a new iteration of the loop
		# as data, the return value will be something like 0x52XXYYZZ, where XXYYZZ is data
		# from the next iteration of the loop.

class TargetRdrandURAM(Target):
	'''
	Target is running rdrand patched to perform
	```
	for (i = 0; i < 0x7FFFF; i++)
		WRITEURAM(i, 0x0x48)
		READURAM(TMP1, i)
		rcx += TMP1
	```
	'''

	op_name = 'rdrand-uram'
	ret_vars = ['summation']
	is_slow = True

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(summation, ) = from_target
		return summation != 0xFFFC0000 and (summation < 0x52000000 or summation > 0x53000000)
		# 					^^^^^^^^^^
		# 32-bit truncation of 0x1FFFFC0000=sum(0x7ffff)

class TargetRdrandURAMCmpSet(Target):
	'''
	Target is running rdrand patched to perform
	```
	for (i = 0; i < 0x7FFFF; i++)
		READURAM(TMP2, 0x48)
		if (TMP2 != 0x5555)
			return 1
	return 0
	```
	'''

	op_name = 'rdrand-uram_cmp_set'
	ret_vars = ['success']
	is_slow = True

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(success, ) = from_target
		return success == 1

class TargetUcodeUpdate(Target):
	'''
	Target is running the ucode update procedure and returns the final ucode revision
	'''

	op_name = 'ucode_update'
	ret_vars = ['ucode_rev', 'time']
	is_slow = True

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(ucode_rev, ) = from_target
		return ucode_rev == 0x28  # My modified ucode is based off rev 0x28, ucode in FIT package is 0x20

class TargetUcodeUpdateTime(Target):
	'''
	Target is running the ucode update procedure and returns how much time (clock cycles) it took
	'''

	# To finish (failing) the ucode update procedure with a modified update file (changed RSA modulus),
	# it takes 4375847 clock cycles. We go for 5000000 and that should be good enough.
	FAILED_UCODE_TIME_MAX = 100000000		# Most of the times I get weird stuff around 828054490, so this is
											# good enough to filter out hex data misinterpreted as time.
	MOD_FAILED_UCODE_TIME_MIN =   5000000
	SIG_FAILED_UCODE_TIME_MIN =   6500000	# Normally it takes ~6.1M to fail the ucode update procedure with an
											# ucode update with different content (signature check fails).

	op_name = 'ucode_update_time'
	ret_vars = ['ucode_rev', 'time']
	is_slow = True

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(_, time, ) = from_target
		return self.SIG_FAILED_UCODE_TIME_MIN < time < self.FAILED_UCODE_TIME_MAX

TargetType: TypeAlias = Target | TargetCmp | TargetLoad | TargetMul | TargetReg | \
			TargetRdrandSubAdd | TargetRdrandAdd | TargetRdrandAddMany | \
			TargetRdrandMovRegs | TargetRdrandLoopAdd | TargetRdrandURAM | \
			TargetRdrandURAMCmpSet | TargetUcodeUpdate | TargetUcodeUpdateTime

def target_op_names() -> list[str]:
	'''
	Returns the names of all target operations.
	'''
	return [TargetMul.op_name, TargetLoad.op_name, TargetCmp.op_name, TargetReg.op_name, \
		 	TargetRdrandSubAdd.op_name, TargetRdrandAdd.op_name, TargetRdrandAddMany.op_name, \
			TargetRdrandMovRegs.op_name, TargetRdrandLoopAdd.op_name, TargetRdrandURAM.op_name, \
			TargetRdrandURAMCmpSet.op_name, TargetUcodeUpdate.op_name, \
			TargetUcodeUpdateTime.op_name]

def target_from_opname(op_name: str) -> TargetType:
	'''
	Returns the target class associated with the given op_name.
	'''
	if op_name == TargetMul.op_name:
		return TargetMul()
	elif op_name == TargetLoad.op_name:
		return TargetLoad()
	elif op_name == TargetCmp.op_name:
		return TargetCmp()
	elif op_name == TargetReg.op_name:
		return TargetReg()
	elif op_name == TargetRdrandSubAdd.op_name:
		return TargetRdrandSubAdd()
	elif op_name == TargetRdrandAdd.op_name:
		return TargetRdrandAdd()
	elif op_name == TargetRdrandAddMany.op_name:
		return TargetRdrandAddMany()
	elif op_name == TargetRdrandMovRegs.op_name:
		return TargetRdrandMovRegs()
	elif op_name == TargetRdrandLoopAdd.op_name:
		return TargetRdrandLoopAdd()
	elif op_name == TargetRdrandURAM.op_name:
		return TargetRdrandURAM()
	elif op_name == TargetRdrandURAMCmpSet.op_name:
		return TargetRdrandURAMCmpSet()
	elif op_name == TargetUcodeUpdate.op_name:
		return TargetUcodeUpdate()
	elif op_name == TargetUcodeUpdateTime.op_name:
		return TargetUcodeUpdateTime()
	else:
		raise ValueError(f'Unknown op_name: {op_name}')
