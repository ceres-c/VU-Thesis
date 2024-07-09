'''
Container for all target code type-related information.
'''

from typing import TypeAlias

# from typing import TypedDict

# class TargetType(TypedDict):
# 	'''
# 	Associates a class of code running on the target with the values sent to the glitcher via UART after a glitch attempt.
# 	'''

# 	mul: list[str]
# 	load: list[str]
# 	cmp: list[str]
# 	rdrand: list[str]

# target_types: TargetType = {
# 	'mul': ['fault_count', 'result_a', 'result_b'],
# 	'load': ['fault_count', 'wrong_value'],
# 	'cmp': ['fault_count'],
# 	'rdrand': ['fault_count'],
# }

# def count_filt(from_target: tuple) -> bool:
# 	'''
# 	Generic filter function that works with all classes returning explicit fault_count
# 	'''
# 	(fault_count, ) = from_target
# 	return fault_count > 0

class Target:
	'''
	Represents the kind of code running on the target.
	'''

	opname = 'unknown'
	ret_vars: list[str] = []

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
	ret_vars = ['fault_count', 'result_a', 'result_b']

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

class TargetRdrandSub(Target):
	'''
	Target is running rdrand patched to perform
	`rcx += rax - rbx`
	'''

	op_name = 'rdrand-sub'
	ret_vars = ['fault_count']

	def is_success(self, from_target: tuple) -> bool:
		'''
		Filter function that determines whether a glitch attempt was successful.
		'''
		(fault_count, ) = from_target
		return fault_count > 0

TargetType: TypeAlias = Target | TargetCmp | TargetLoad | TargetMul | TargetRdrandSub

def target_op_names() -> list[str]:
	'''
	Returns the names of all target operations.
	'''
	return [TargetMul.opname, TargetLoad.opname, TargetCmp.opname, TargetRdrandSub.op_name]

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
	elif opname == TargetRdrandSub.op_name:
		return TargetRdrandSub()
	else:
		raise ValueError(f'Unknown opname: {opname}')
