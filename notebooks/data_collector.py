#! /usr/bin/env python3

import pathlib
import sys
from argparse import ArgumentParser, Namespace
import sqlite3
from sqlite3 import Error
import time

import picocoder_client
from picocoder_client import Picocoder, GlitchController, GlitchControllerTPS65094, GlitchResult, TargetType
from picocoder_client import PowerSupply, KA3305P

GLITCHER_BAUD = 115200

class GlitchSQLite():
	def __init__(self, db_name: str, table_name: str, settings: str, extra: str):
		'''
		Args:
			db_name (str): Database filename
			table_name (str): Table name (some name that identifies this glitch campaign)
			settings (str): Settings string (e.g. `ext_offset=100:300(1),width=75:125(1),voltage=35:36(1),prep_voltage=42(1)`)
			extra (str): Extra string that helps in identifying the experiment (e.g. target software commit hash)
		'''
		self.db_name: str = db_name
		self.table_name: str = table_name
		self.settings: str = settings
		self.extra: str = extra
		self.conn: sqlite3.Connection = sqlite3.connect(db_name)
		self.c: sqlite3.Cursor = self.conn.cursor()
		if not self.has_table('settings'):
			self.c.execute('CREATE TABLE settings (table_name TEXT PRIMARY KEY, settings TEXT, extra TEXT)')
		if not self.has_table('runtimes'):
			self.c.execute('CREATE TABLE runtimes (table_name TEXT PRIMARY KEY, runtime REAL)')

	def __del__(self):
		self.close()

	def has_table(self, table_name: str = '') -> bool:
		'''
		Check if a table exists in the database

		Args:
			table_name (str): Table name to check for. If empty, it will check for the default table name
		'''
		self.c.execute(f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table_name if table_name else self.table_name}"')
		return self.c.fetchone() is not None

	def get_settings(self, table_name: str = '') -> tuple[str, str]:
		'''
		Get settings and extra associated with a table name

		Args:
			table_name (str): Table name to get settings from. If empty, it will get settings from the default table name

		Returns:
			(str, str): settings, extra
		'''
		self.c.execute(f'SELECT settings, extra FROM settings WHERE table_name="{table_name if table_name else self.table_name}"')
		return self.c.fetchone()

	def count_rows(self, table_name: str = '') -> int:
		'''
		Count the number of rows in a table

		Args:
			table_name (str): Table name to count rows from. If empty, it will count rows from the default table name
		'''
		self.c.execute(f'SELECT COUNT(*) FROM {table_name if table_name else self.table_name}')
		return self.c.fetchone()[0]

	def create_table(self, target_type: TargetType) -> None:

		query  = f'CREATE TABLE {self.table_name} '
		query += '(ext_offset INTEGER, width INTEGER, voltage INTEGER, prep_voltage INTEGER, result STRING, data BLOB'
		for var in target_type.ret_vars:
			query += f', {var} INTEGER'
		query += ')'
		self.c.execute(query)
		self.c.execute('INSERT INTO settings VALUES (?, ?, ?)', (self.table_name, self.settings, self.extra))
		self.conn.commit()

	def insert_result(self, target_type: TargetType,
				   ext_offset: int, width: int, voltage: int, prep_voltage: int, result: GlitchResult,
				   data: tuple|bytes|None = b'', ) -> None:
		'''
		Insert a result into the database

		Args:
			target_type (TargetType): Target type
			ext_offset (int): External offset
			width (int): Width
			voltage (int): Glitch voltage
			prep_voltage (int): Preparation voltage
			result (GlitchResult): Glitch result
			data (tuple|bytes|None): Data associated with the result
		'''

		if type(data) is tuple:
			data_tuple = data
			data_blob = b''
		elif type(data) is bytes:
			data_tuple = tuple([0] * target_type.ret_count)
			data_blob = data
		elif data is None:
			data_tuple = tuple([0] * target_type.ret_count)
			data_blob = b''
		else:
			raise ValueError(f'Invalid data type {type(data)}')

		query = f'INSERT INTO {self.table_name} VALUES (?, ?, ?, ?, ?, ?' # ext_offset, width, voltage, prep_voltage, result, data
		query += ', ?' * target_type.ret_count
		query += ')'
		self.c.execute(query, (ext_offset, width, voltage, prep_voltage, result.name, data_blob, *data_tuple))
		self.conn.commit()

	def set_runtime(self, runtime: float) -> None: # Inserts or increases the runtime
		self.c.execute(f'INSERT INTO runtimes(table_name, runtime) VALUES(?, ?) ON CONFLICT(table_name) DO UPDATE SET runtime=runtime+{runtime}', (self.table_name, runtime))
		self.conn.commit()

	def set_schema(self, schema: str) -> None:
		self.c.execute(f'CREATE TABLE {self.table_name} {schema}')
		self.conn.commit()

	def close(self) -> None:
		self.conn.close()



def reset_target(ps: PowerSupply, glitcher: Picocoder, retries: int = 3) -> None:
	for _ in range(retries):
		ps.power_cycle()
		if glitcher.ping_target():
			break
	else:
		raise ConnectionError('Target not responding after reset')

def settings_to_str(ext_offset: list, width: list, voltage: list, prep_voltage: list) -> str:
	ret = 'ext_offset'
	if ext_offset[0] == ext_offset[1]:
		ret += f'={ext_offset[0]}'
	else:
		ret += f'={ext_offset[0]}:{ext_offset[1]}'
		ret += f'({ext_offset[2]})'
	ret += ',width'
	if width[0] == width[1]:
		ret += f'={width[0]}'
	else:
		ret += f'={width[0]}:{width[1]}'
		ret += f'({width[2]})'
	ret += ',voltage'
	if voltage[0] == voltage[1]:
		ret += f'={voltage[0]}'
	else:
		ret += f'={voltage[0]}:{voltage[1]}'
		ret += f'({voltage[2]})'
	ret += ',prep_voltage'
	if prep_voltage[0] == prep_voltage[1]:
		ret += f'={prep_voltage[0]}'
	else:
		ret += f'={prep_voltage[0]}:{prep_voltage[1]}'
		ret += f'({prep_voltage[2]})'
	return ret

def glitch_loop(
			db: GlitchSQLite,
			ps: PowerSupply,
			gc: GlitchController,
			glitcher: Picocoder,
			stop_half_success: bool,
			stop_success: bool
		) -> int:
	start_time = time.time()
	for i, gs in enumerate(gc.rand_glitch_values()):
		if i % 5 == 0:
			print(f'Iteration {i}, rate {i/(time.time()-start_time):.2f}Hz         ', end='\r', flush=True) # spaces to overwrite prev line
		try:
			result, data = glitcher.glitch(gs)
			db.insert_result(glitcher.tc, gs['ext_offset'], gs['width'], gs['voltage'], gs['prep_voltage'], result, data)

			if stop_half_success and result == GlitchResult.HALF_SUCCESS:
				print('Half-success detected, stopping. Target is left in its current state')
				break
			if stop_success and result == GlitchResult.SUCCESS:
				print('Success detected, stopping. Target is left in its current state')
				break

			if result in [GlitchResult.RESET, GlitchResult.BROKEN, GlitchResult.HALF_SUCCESS]:
				try:
					reset_target(ps, glitcher)
				except ConnectionError:
					print('Failed to reset target, shutting down')
					ps.on = False
					return 1

		except KeyboardInterrupt:
			end_time = time.time()
			print(f'\nExiting. Total runtime: {end_time-start_time:.2f}s')
			db.set_runtime(end_time-start_time)
			ps.power_cycle()
			break
	return 0

def main(a: Namespace) -> int:
	settings_str = settings_to_str(a.ext_offset, a.width, a.voltage, a.prep_voltage)
	db = GlitchSQLite(a.db_file, a.db_table, settings_str, a.extra_descr)
	if db.has_table():
		count = db.count_rows()
		resp = input(f'Table {a.db_table} already exists in {a.db_file} with {count} rows. Append to it? [Y/n] ')
		if resp.lower() != 'y' and resp.lower() != '':
			return 1
	else:
		db.create_table(picocoder_client.target_from_opname(a.operation))

	ps = KA3305P(port=a.power_supply_port, cycle_wait=0.5)
	ps.con()
	ps.power_cycle()

	glitcher = Picocoder(a.glitcher_port, GLITCHER_BAUD)
	glitcher.tc = picocoder_client.target_from_opname(a.operation)
	if not glitcher.ping():
		raise ConnectionError('Glitcher not responding')
	if not glitcher.ping_target():
		raise ConnectionError('Target not responding')

	max_total_duration = glitcher.measure_loop_duration()
	if max_total_duration < 0:
		raise ValueError(f'Invalid duration {max_total_duration}')
	if a.ext_offset[2] + a.width[2] > max_total_duration:
		raise ValueError(f'Max ext_offset + max width > max_total_duration: ({a.ext_offset[2]} + {a.width[2]} > {max_total_duration})')

	gc = GlitchControllerTPS65094(groups=[r.name for r in GlitchResult], parameters=['ext_offset', 'width', 'voltage', 'prep_voltage'], nominal_voltage=1.24)
	gc.set_range('ext_offset', a.ext_offset[0], a.ext_offset[1])
	gc.set_step('ext_offset', a.ext_offset[2])
	gc.set_range('width', a.width[0], a.width[1])
	gc.set_step('width', a.width[2])
	gc.set_range('voltage', a.voltage[0], a.voltage[1])
	gc.set_step('voltage', a.voltage[2])
	gc.set_range('prep_voltage', a.prep_voltage[0], a.prep_voltage[1])
	gc.set_step('prep_voltage', a.prep_voltage[2])

	glitch_loop(db, ps, gc, glitcher, a.stop_half_success, a.stop_success)
	return 0

if __name__ == '__main__':
	argparser = ArgumentParser(description='Simple script to run a glitch campaign and save results to a database')
	argparser.add_argument('db_file', default='glitch_results.db', type=str, help='Database file name')
	argparser.add_argument('db_table', type=str, help='Database table name (e.g. target commit hash) - Don\'t name it `; OR 1=1` please')
	argparser.add_argument('operation', type=str, choices=picocoder_client.target_op_names(), help='The operation to glitch')
	argparser.add_argument('--power-supply-port', default='/dev/ttyACM0', type=str, help='Power supply serial port (default /dev/ttyACM0)')
	argparser.add_argument('--glitcher-port', default='/dev/ttyACM1', type=str, help='Glitcher serial port (default /dev/ttyACM1)')
	argparser.add_argument('--ext-offset', nargs=3, type=int, metavar=('start', 'end', 'step'), help='External offset range', required=True)
	argparser.add_argument('--width', nargs=3, type=int, metavar=('start', 'end', 'step'), help='Width range', required=True)
	argparser.add_argument('--voltage', nargs=3, type=int, metavar=('start', 'end', 'step'), help='Glitch voltage range', required=True)
	argparser.add_argument('--prep-voltage', default=[0b0101010,0b0101010,1], nargs=3, type=int, metavar=('start', 'end', 'step'), help='Preparation voltage (default 0b0101010 = 0.91V)')
	argparser.add_argument('--extra-descr', default='', type=str, help='Description of the glitch campaign (e.g. target software commit hash)')
	argparser.add_argument('-s', '--stop-half-success', default=False, action='store_true', help='Stop the glitch campaign if a half-success is detected')
	argparser.add_argument('-S', '--stop-success', default=False, action='store_true', help='Stop the glitch campaign if a success is detected')
	args = argparser.parse_args()

	exit(main(args))
