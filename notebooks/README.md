# Software
In this folder you will find the software component of picocoder.

## Database
You can download [here](https://mega.nz/file/2plRWQwC#RJ_q7kaOB3b-htbncqA-zl1y91dWcVw2RyKrIw8kXjc) a database with my experimental data.

## Notebooks
The notebooks are used to visualize the data collected by the pi pico and
identify interesting glitching points

## Data collector
The data collector is a python script that can be run headlessly and store
results in in a SQLite database. Run `data_collector.py --help` for more
information.

## Library files
`glitch_utils.py` is the main file that handles the communication with the pi
pico and the target, and wraps all the glitching logic.

`power_supply.py` is a helper to expose a common interface to the control
script (be it the notebook or the data collector) to control the power supply.
It includes an abstract class that can be implemented for different power,
currently it supports only the KORAD KA3005P power supply that I used.
