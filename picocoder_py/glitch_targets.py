'''
Container for all target code type-related information.
'''

from typing import TypeAlias

class Target:
	'''
	Represents the kind of code running on the target.
	'''

	opname: str = 'unknown'
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

	opname = 'mul'
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

	opname = 'load'
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

	opname = 'cmp'
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

	opname = 'reg'
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

class TargetUcodeUpdate(Target):
	'''
	Target is running the ucode update procedure and returns the final ucode revision
	'''

	opname = 'ucode_update'
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

	opname = 'ucode_update_time'
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
			TargetRdrandMovRegs | TargetUcodeUpdate | TargetUcodeUpdateTime

def target_op_names() -> list[str]:
	'''
	Returns the names of all target operations.
	'''
	return [TargetMul.opname, TargetLoad.opname, TargetCmp.opname, TargetReg.opname, \
		 	TargetRdrandSubAdd.op_name, TargetRdrandAdd.op_name, TargetRdrandAddMany.op_name, \
			TargetRdrandMovRegs.op_name, TargetUcodeUpdate.opname, TargetUcodeUpdateTime.opname]

def target_from_opname(opname: str) -> TargetType:
	'''
	Returns the target class associated with the given opname.
	'''
	if opname == TargetMul.opname:
		return TargetMul()
	elif opname == TargetLoad.opname:
		return TargetLoad()
	elif opname == TargetCmp.opname:
		return TargetCmp()
	elif opname == TargetReg.opname:
		return TargetReg()
	elif opname == TargetRdrandSubAdd.op_name:
		return TargetRdrandSubAdd()
	elif opname == TargetRdrandAdd.op_name:
		return TargetRdrandAdd()
	elif opname == TargetRdrandAddMany.op_name:
		return TargetRdrandAddMany()
	elif opname == TargetRdrandMovRegs.op_name:
		return TargetRdrandMovRegs()
	elif opname == TargetUcodeUpdate.opname:
		return TargetUcodeUpdate()
	elif opname == TargetUcodeUpdateTime.opname:
		return TargetUcodeUpdateTime()
	else:
		raise ValueError(f'Unknown opname: {opname}')
