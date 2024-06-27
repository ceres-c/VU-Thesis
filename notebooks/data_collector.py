#! /usr/bin/env python3

from argparse import ArgumentParser
import sqlite3
from sqlite3 import Error
import time

import glitch_utils
from glitch_utils import Picocoder, GlitchResult
from power_supply import PowerSupply, KA3305P

GLITCHER_BAUD = 115200

class GlitchSQLite():
	def __init__(self, db_name: str, table_name: str):
		self.db_name = db_name
		self.table_name = table_name
		self.conn = sqlite3.connect(db_name)
		self.c = self.conn.cursor()

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

	def create_table(self) -> None:
		self.c.execute(f'CREATE TABLE {self.table_name} (ext_offset INTEGER, width INTEGER, voltage INTEGER, prep_voltage INTEGER, result STRING, data BLOB, successes INTEGER, result_a INTEGER, result_b INTEGER)')
		self.conn.commit()

	def insert_result(self,
				   ext_offset: int, width: int, voltage: int, prep_voltage: int, result: str,
				   data: bytes|None = b'', successes: int = 0, result_a: int = 0, result_b: int = 0) -> None:
		if data is None:
			data = b''
		self.c.execute(f'INSERT INTO {self.table_name} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (ext_offset, width, voltage, prep_voltage, result, data, successes, result_a, result_b))
		self.conn.commit()

	def set_schema(self, schema: str) -> None:
		self.c.execute(f'CREATE TABLE {self.table_name} {schema}')
		self.conn.commit()

	def close(self) -> None:
		self.conn.close()



def reset_target(ps: PowerSupply, glitcher: Picocoder) -> None:
	ps.power_cycle()
	if not glitcher.ping_target():
		raise ConnectionError('Target not responding after reset')

def main(db_name:str, table_name: str, power_supply_port: str, glitcher_port: str, ext_offset: list, width: list, voltage: list, prep_voltage: list) -> int:
	db = GlitchSQLite(db_name, table_name)
	if db.has_table():
		resp = input(f'Table {table_name} already exists in {db_name}. Append to it? [Y/n] ')
		if resp.lower() != 'y' and resp.lower() != '':
			return 1
	else:
		db.create_table()

	ps = KA3305P(port=power_supply_port, cycle_wait=0.5)
	ps.con()
	ps.power_cycle()

	glitcher = glitch_utils.Picocoder(glitcher_port, GLITCHER_BAUD)
	if not glitcher.ping():
		raise ConnectionError('Glitcher not responding')
	if not glitcher.ping_target():
		raise ConnectionError('Target not responding')

	max_total_duration = glitcher.measure_loop_duration()
	if max_total_duration < 0:
		raise ValueError(f'Invalid duration {max_total_duration}')
	if ext_offset[2] + width[2] > max_total_duration:
		raise ValueError(f'Max ext_offset + max width > max_total_duration: ({ext_offset[2]} + {width[2]} > {max_total_duration})')

	gc = glitch_utils.GlitchControllerTPS65094(groups=[r.name for r in GlitchResult], parameters=['ext_offset', 'width', 'voltage', 'prep_voltage'])
	gc.set_range('ext_offset', ext_offset[0], ext_offset[1])
	gc.set_step('ext_offset', ext_offset[2])
	gc.set_range('width', width[0], width[1])
	gc.set_step('width', width[2])
	gc.set_range('voltage', voltage[0], voltage[1])
	gc.set_step('voltage', voltage[2])
	gc.set_range('prep_voltage', prep_voltage[0], prep_voltage[1])
	gc.set_step('prep_voltage', prep_voltage[2])

	start = time.time()
	for i, gs in enumerate(gc.rand_glitch_values()):
		if i % 5 == 0:
			print(f'Iteration {i}, rate {i/(time.time()-start):.2f}Hz', end='\r', flush=True)
		try:
			read_result, read_data = glitcher.glitch_mul(gs)
			if read_result == GlitchResult.SUCCESS:
				[successes, result_a, result_b] = read_data
				db.insert_result(gs['ext_offset'], gs['width'], gs['voltage'], gs['prep_voltage'], read_result.name, successes=successes, result_a=result_a, result_b=result_b)
			else:
				db.insert_result(gs['ext_offset'], gs['width'], gs['voltage'], gs['prep_voltage'], read_result.name, data=read_data)

			if read_result in [GlitchResult.RESET, GlitchResult.BROKEN, GlitchResult.HALF_SUCCESS]:
				reset_target(ps, glitcher)
		except KeyboardInterrupt:
			print(f'\nExiting. Total runtime: {time.time()-start:.2f}s')
			ps.power_cycle()
			return 0

if __name__ == '__main__':
	argparser = ArgumentParser(description='Simple script to run a glitch campaign and save results to a database')
	argparser.add_argument('db_file', default='glitch_results.db', type=str, help='Database file name')
	argparser.add_argument('db_table', type=str, help='Database table name (e.g. target commit hash) - Don\'t name it `; OR 1=1` please')
	argparser.add_argument('--power-supply', default='/dev/ttyACM0', type=str, help='Power supply serial port (default /dev/ttyACM0)')
	argparser.add_argument('--glitcher', default='/dev/ttyACM1', type=str, help='Glitcher serial port (default /dev/ttyACM1)')
	argparser.add_argument('--ext-offset', nargs=3, type=int, metavar=('start', 'end', 'step'), help='External offset range', required=True)
	argparser.add_argument('--width', nargs=3, type=int, metavar=('start', 'end', 'step'), help='Width range', required=True)
	argparser.add_argument('--voltage', nargs=3, type=int, metavar=('start', 'end', 'step'), help='Glitch voltage range', required=True)
	argparser.add_argument('--prep-voltage', default=[0b0101010,0b0101010,1], nargs=3, type=int, metavar=('start', 'end', 'step'), help='Preparation voltage (default 0b0101010 = 0.91V)')
	args = argparser.parse_args()

	exit(main(args.db_file, args.db_table, args.power_supply, args.glitcher, args.ext_offset, args.width, args.voltage, args.prep_voltage))
