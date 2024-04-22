/* According to Serial Flasher Protocol Specification - version 1 */
#define S_ACK 0x06
#define S_NAK 0x15
#define S_CMD_NOP			0x00	/* No operation									*/
#define S_CMD_Q_IFACE		0x01	/* Query interface version						*/
#define S_CMD_Q_CMDMAP		0x02	/* Query supported commands bitmap				*/
#define S_CMD_Q_PGMNAME		0x03	/* Query programmer name						*/
#define S_CMD_Q_SERBUF		0x04	/* Query Serial Buffer Size						*/
#define S_CMD_Q_BUSTYPE		0x05	/* Query supported bustypes						*/
#define S_CMD_Q_CHIPSIZE	0x06	/* Query supported chipsize (2^n format)		*/
#define S_CMD_Q_OPBUF		0x07	/* Query operation buffer size					*/
#define S_CMD_Q_WRNMAXLEN	0x08	/* Query Write to opbuf: Write-N maximum length	*/
#define S_CMD_R_BYTE		0x09	/* Read a single byte							*/
#define S_CMD_R_NBYTES		0x0A	/* Read n bytes									*/
#define S_CMD_O_INIT		0x0B	/* Initialize operation buffer					*/
#define S_CMD_O_WRITEB		0x0C	/* Write opbuf: Write byte with address			*/
#define S_CMD_O_WRITEN		0x0D	/* Write to opbuf: Write-N						*/
#define S_CMD_O_DELAY		0x0E	/* Write opbuf: udelay							*/
#define S_CMD_O_EXEC		0x0F	/* Execute operation buffer						*/
#define S_CMD_SYNCNOP		0x10	/* Special no-operation that returns NAK+ACK	*/
#define S_CMD_Q_RDNMAXLEN	0x11	/* Query read-n maximum length					*/
#define S_CMD_S_BUSTYPE		0x12	/* Set used bustype(s).							*/
#define S_CMD_O_SPIOP		0x13	/* Perform SPI operation.						*/
#define S_CMD_S_SPI_FREQ	0x14	/* Set SPI clock frequency						*/
#define S_CMD_S_PIN_STATE	0x15	/* Enable/disable output drivers				*/

// picocode glitching commands
#define P_CMD_ARM			0x20	/* Enable glitch handler						*/
#define P_CMD_SET_EXT_OFFST	0x21	/* Set external offset (wait after trigger)		*/
#define P_CMD_SET_WIDTH		0x22	/* Set glitch width								*/

// picocode glitch results
#define P_CMD_RESULT_RESET	0x30	/* Target reset									*/
#define P_CMD_RESULT_ALIVE	0x31	/* Target alive (data will follow)				*/
#define P_CMD_RESULT_WEIRD	0x32	/* Target weird									*/

// Commands to/from the target board
#define T_CMD_RESET			'R'
#define T_CMD_CONNECT		'C'
#define T_CMD_TRIGGER		'T'
#define T_CMD_ALIVE			'A'
#define T_CMD_BOGUS1		0xF0	/* Unknown to the target, will reset target		*/
#define T_CMD_BOGUS2		0xF1
#define T_CMD_BOGUS3		0xF2
