/* According to Serial Flasher Protocol Specification - version 1 */
#define S_ACK						0x06
#define S_NAK						0x15
#define S_CMD_NOP					0x00	/* No operation									*/
#define S_CMD_Q_IFACE				0x01	/* Query interface version						*/
#define S_CMD_Q_CMDMAP				0x02	/* Query supported commands bitmap				*/
#define S_CMD_Q_PGMNAME				0x03	/* Query programmer name						*/
#define S_CMD_Q_SERBUF				0x04	/* Query Serial Buffer Size						*/
#define S_CMD_Q_BUSTYPE				0x05	/* Query supported bustypes						*/
#define S_CMD_Q_CHIPSIZE			0x06	/* Query supported chipsize (2^n format)		*/
#define S_CMD_Q_OPBUF				0x07	/* Query operation buffer size					*/
#define S_CMD_Q_WRNMAXLEN			0x08	/* Query Write to opbuf: Write-N maximum length	*/
#define S_CMD_R_BYTE				0x09	/* Read a single byte							*/
#define S_CMD_R_NBYTES				0x0A	/* Read n bytes									*/
#define S_CMD_O_INIT				0x0B	/* Initialize operation buffer					*/
#define S_CMD_O_WRITEB				0x0C	/* Write opbuf: Write byte with address			*/
#define S_CMD_O_WRITEN				0x0D	/* Write to opbuf: Write-N						*/
#define S_CMD_O_DELAY				0x0E	/* Write opbuf: udelay							*/
#define S_CMD_O_EXEC				0x0F	/* Execute operation buffer						*/
#define S_CMD_SYNCNOP				0x10	/* Special no-operation that returns NAK+ACK	*/
#define S_CMD_Q_RDNMAXLEN			0x11	/* Query read-n maximum length					*/
#define S_CMD_S_BUSTYPE				0x12	/* Set used bustype(s).							*/
#define S_CMD_O_SPIOP				0x13	/* Perform SPI operation.						*/
#define S_CMD_S_SPI_FREQ			0x14	/* Set SPI clock frequency						*/
#define S_CMD_S_PIN_STATE			0x15	/* Enable/disable output drivers				*/

// picocode glitching commands
#define P_CMD_ARM					0x20	/* Enable glitch handler						*/

#define P_CMD_FORCE					0x30	/* Force write to PMBus to perform a glitch		*/
#define P_CMD_SET_VOLTAGE			0x31	/* Set glitch voltage							*/
#define P_CMD_SET_EXT_OFFST			0x32	/* Set external offset (wait after trig.) in us	*/
#define P_CMD_SET_WIDTH				0x33	/* Set glitch width	(duration of glitch) in us	*/
#define P_CMD_SET_PREP_VOLTAGE		0x34	/* Set Vp (preparation voltage) before glitch	*/

// picocode glitch results
#define P_CMD_RESULT_RESET			0x50	/* Target reset									*/
#define P_CMD_RESULT_ALIVE			0x51	/* Target is alive								*/
#define P_CMD_RESULT_ZOMBIE			0x52	/* Target is nor alive nor it reset after glitch */
#define P_CMD_RESULT_DATA_TIMEOUT	0x53	/* Target timeout after glitch when sending data back (target is alive) */
#define P_CMD_RESULT_UNREACHABLE	0x54	/* Target unavailable when starting glitch: did not receive anything on the serial port */
#define P_CMD_RESULT_PMIC_FAIL		0x55	/* Could not send command to PMIC				*/
#define P_CMD_RESULT_ANSI_CTRL_CODE	0x56	/* Target sent an ANSI control code, data will follow */

// picocode command responses
#define P_CMD_RETURN_OK				0x61	/* Command successful							*/
#define P_CMD_RETURN_KO				0x62	/* Command failed								*/
#define P_CMD_PONG					0x63	/* Response to ping								*/

// Misc
#define P_CMD_PING					0x70	/* Ping from host to picocoder					*/
#define P_CMD_TARGET_PING			0x71	/* Ping from picocoder to target				*/
#define P_CMD_TARGET_PING_SLOW		0x72	/* Ping from picocoder to target for slow targets (e.g. ucode update) */
#define P_CMD_UART_ECHO				0x75	/* Echo UART data from target to USB			*/
#define P_CMD_MEASURE_LOOP_DURATION	0x76	/* Measure the length (in us) of opcode loop	*/
#define P_CMD_UART_TOGGLE_DEBUG_PIN	0x77	/* Toggle debug pin on UART data in				*/
#define P_CMD_DEBUG_PULSE			0x78	/* Single 10 us pulse on debug pin				*/

// Commands to/from the target board
#define T_CMD_READY					'R'		/* The target is alive and ready				*/
#define T_CMD_DONE					'D'		/* Done with the current loop iteration			*/
#define T_CMD_ANSI_ESC				0x1B	/* ANSI escape code - preamble to coreboot debug output */
