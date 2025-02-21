#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from mayavi import mlab
from tvtk.api import tvtk
import numpy as np
import sqlite3
from picocoder_client import GlitchResult

conn: sqlite3.Connection = sqlite3.connect('/tmp/glitch2.db')
c: sqlite3.Cursor = conn.cursor()

def get_settings(table_name: str = '') -> tuple[str, str]:
	'''
	Get settings and extra associated with a table name

	Args:
		table_name (str): Table name to get settings from. If empty, it will get settings from the default table name

	Returns:
		(str, str): settings, extra
	'''
	c.execute(f'SELECT settings, extra FROM settings WHERE table_name="{table_name}"')
	return c.fetchone()






# Example functions and objects assumed to be defined elsewhere:
# - get_settings(data_source_table) returns (settings, extra_descr)
# - GlitchResult.SUCCESS.name is the string indicating success.
# - c is a sqlite3.Cursor for your database.
#
# For example:
# conn = sqlite3.connect('mydatabase.db')
# c = conn.cursor()

def draw_cube(x0, y0, z0, dx, dy, dz, color=(0, 0, 1)):
	"""
	Creates a cube (rectangular prism) with lower corner at (x0, y0, z0)
	and dimensions (dx, dy, dz), and adds it to the current Mayavi scene.
	"""
	cube_source = tvtk.CubeSource(x_length=dx, y_length=dy, z_length=dz)
	# The CubeSource by default centers the cube at the origin;
	# adjust the center so that the cube’s lower corner is at (x0, y0, z0).
	cube_source.center = (x0 + dx / 2, y0 + dy / 2, z0 + dz / 2)

	cube_mapper = tvtk.PolyDataMapper(input_connection=cube_source.output_port)
	cube_actor = tvtk.Actor(mapper=cube_mapper)
	cube_actor.property.color = color
	mlab.gcf().scene.add_actor(cube_actor)

def plot_hist_rsa_modulus_3d_mayavi(data_source_table: str, png_export: bool):
	# Retrieve settings (and extra_descr if needed)
	settings, extra_descr = get_settings(data_source_table)

	# Query the database for rows with a successful result.
	c.execute(f'SELECT * FROM {data_source_table} WHERE result == ?', (GlitchResult.SUCCESS.name,))
	columns = [col for (col, *_) in c.description]
	rows = c.fetchall()

	if 'time' not in columns:
		print('No time column found, run this on rsa modulus tests')
		return

	# Extract data for the histogram (ignoring outliers).
	data_ext = []
	data_time = []
	for row in rows:
		row_dict = dict(zip(columns, row))
		if row_dict['time'] < 70000000:  # Remove outliers
			data_ext.append(row_dict['ext_offset'])
			data_time.append(row_dict['time'])

	# Compute a 2D histogram over (ext_offset, time) with 35 bins on each axis.
	hist, xedges, yedges = np.histogram2d(data_ext, data_time, bins=35)

	# Create a new Mayavi figure.
	mlab.figure(size=(800, 600), bgcolor=(1, 1, 1))

	# Add a title using mlab.text (coordinates are normalized).
	mlab.text(0.01, 0.95, f'{data_source_table}\n{",".join(settings)}', width=0.4)

	# Determine bin sizes (assuming uniform bins).
	dx = np.diff(xedges)[0]
	dy = np.diff(yedges)[0]

	# Loop over each histogram bin and draw a cube where the count is nonzero.
	for i in range(hist.shape[0]):
		for j in range(hist.shape[1]):
			count = hist[i, j]
			if count > 0:
				x0 = xedges[i]
				y0 = yedges[j]
				# Here, z0 is 0 (base of the bar) and the height (dz) is the count.
				draw_cube(x0, y0, 0, dx, dy, count, color=(0, 0, 1))

	# Add axes and an outline for context.
	mlab.axes(xlabel='ext_offset', ylabel='Time (rdtsc)', zlabel='Count')
	mlab.outline()

	# Optionally export the scene as a PNG.
	if png_export:
		mlab.savefig(f"{data_source_table}.png")

	mlab.show()

# Example call:
plot_hist_rsa_modulus_3d_mayavi('_8Gb_86ab61e_rsamod_2', png_export=False)
