/*
 * PicoCoder: Raspberry Pi Pico microcode glitcher
 * Serprog code and command handling are taken from Thomas Roth's pico-serprog
 */

#include "picocoder.h"
#include "cmd.h"
#include "spi.h"
#include "glitch.h"
#include "pmbus.h"

uint32_t getu24() {
	uint32_t c1 = getchar();
	uint32_t c2 = getchar();
	uint32_t c3 = getchar();
	return c1 | (c2<<8) | (c3<<16);
}

uint32_t getu32() {
	uint32_t c1 = getchar();
	uint32_t c2 = getchar();
	uint32_t c3 = getchar();
	uint32_t c4 = getchar();
	return c1 | (c2<<8) | (c3<<16) | (c4<<24);
}

void putu32(uint32_t d) {
	putchar(d & 0xFF);
	putchar((d >> 8) & 0xFF);
	putchar((d >> 16) & 0xFF);
	putchar((d >> 24) & 0xFF);
}

unsigned char write_buffer[4096];

void process(pio_spi_inst_t *spi, int command) {
	switch(command) {
		case S_CMD_NOP:
			putchar(S_ACK);
			break;
		case S_CMD_Q_IFACE:
			putchar(S_ACK);
			putchar(0x01);
			putchar(0x00);
			break;
		case S_CMD_Q_CMDMAP:
			putchar(S_ACK);
			putu32(S_CMD_MAP);

			for(int i = 0; i < 32 - sizeof(uint32_t); i++) {
				putchar(0);
			}
			break;
		case S_CMD_Q_PGMNAME:
			putchar(S_ACK);
			fwrite("pico-serprog\x0\x0\x0\x0\x0", 1, 16, stdout);
			fflush(stdout);
			break;
		case S_CMD_Q_SERBUF:
			putchar(S_ACK);
			putchar(0xFF);
			putchar(0xFF);
			break;
		case S_CMD_Q_BUSTYPE:
			putchar(S_ACK);
			putchar(S_SUPPORTED_BUS);
			break;
		case S_CMD_SYNCNOP:
			putchar(S_NAK);
			putchar(S_ACK);
			break;
		case S_CMD_S_BUSTYPE:
			{
				int bustype = getchar();
				if((bustype | S_SUPPORTED_BUS) == S_SUPPORTED_BUS) {
					putchar(S_ACK);
				} else {
					putchar(S_NAK);
				}
			}
			break;
		case S_CMD_O_SPIOP:
			{

				uint32_t wlen = getu24();
				uint32_t rlen = getu24();

				cs_select(PIN_SPI_CS);
				fread(write_buffer, 1, wlen, stdin);
				pio_spi_write8_blocking(spi, write_buffer, wlen);

				putchar(S_ACK);
				uint32_t chunk;
				char buf[128];

				for(uint32_t i = 0; i < rlen; i += chunk) {
					chunk = MIN(rlen - i, sizeof(buf));
					pio_spi_read8_blocking(spi, buf, chunk);
					fwrite(buf, 1, chunk, stdout);
					fflush(stdout);
				}

				cs_deselect(PIN_SPI_CS);
			}
			break;
		case S_CMD_S_SPI_FREQ:
			{
				uint32_t freq = getu32();
				if (freq >= 1) {
					putchar(S_ACK);
					putu32(serprog_spi_init(spi, freq));
				} else {
					putchar(S_NAK);
				}
			}
			break;
		case S_CMD_S_PIN_STATE:
			//TODO:
			getchar();
			putchar(S_ACK);
			break;
		case P_CMD_ARM:
			glitcher_arm();
			break;
		case P_CMD_DISARM:
			glitcher_disarm();
			break;
		case P_CMD_UART_ECHO:
			uart_echo();
			break;
		case P_CMD_I2C_WRITE:
			uart_level_shifter_enable();
			putchar('X');
			uart_putc(UART_TARGET, 'X');
			uint8_t pmbus_cmd_glitch[TPS_WRITE_REG_CMD_LEN] = {TPS_REG_BUCK2CTRL, TPS_VCORE_MIN};
			int write_glitch_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, pmbus_cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
			uart_level_shifter_disable();
			break;
		default:
			putchar(S_NAK);
	}
}

static pio_spi_inst_t spi = {
	.pio = SPI_PIO,
	.sm = 0,
	.cs_pin = PIN_SPI_CS
};

int main() {
	// Metadata for picotool
	bi_decl(bi_program_description("PicoCoder: Rasperry Pi Pico microcode glitcher"));
	bi_decl(bi_program_url("https://github.com/ceres-c/VU-Thesis/"));
	bi_decl(bi_1pin_with_name(PIN_UART_TX, "TX"));
	bi_decl(bi_1pin_with_name(PIN_UART_RX, "RX"));
	bi_decl(bi_1pin_with_name(PIN_UART_OE, "OE"));
	bi_decl(bi_1pin_with_name(PIN_PMBUS_SDA, "SDA"));
	bi_decl(bi_1pin_with_name(PIN_PMBUS_SCL, "SCL"));
	bi_decl(bi_1pin_with_name(PIN_LED, "LED"));
	bi_decl(bi_1pin_with_name(PIN_SPI_MISO, "MISO"));
	bi_decl(bi_1pin_with_name(PIN_SPI_MOSI, "MOSI"));
	bi_decl(bi_1pin_with_name(PIN_SPI_SCK, "SCK"));
	bi_decl(bi_1pin_with_name(PIN_SPI_CS, "CS#"));

	stdio_init_all();

	stdio_set_translate_crlf(&stdio_usb, false);

	// Initialize all peripherals
	target_uart_init();					// UART:	RPi <-> coreboot (115200 baud)
	// gpio_disable_pulls(PIN_PMBUS_SDA);	// Don't add extra pulls, let the CPU handle it
	// gpio_disable_pulls(PIN_PMBUS_SCL);
	gpio_set_pulls(PIN_PMBUS_SDA, true, false);
	gpio_set_pulls(PIN_PMBUS_SCL, true, false);
	i2c_init(I2C_PMBUS, 1000000);		// PMBus:	CPU <-> PMIC (1 MHz)
	serprog_spi_init(&spi, 1000000);	// Serprog:	RPi <-> BIOS flash (1 MHz)
	gpio_init(PIN_LED);					// Command processing LED
	gpio_set_dir(PIN_LED, GPIO_OUT);

	// Command handling
	while(1) {
		int command = getchar();

		gpio_put(PIN_LED, 1);
		process(&spi, command);
		gpio_put(PIN_LED, 0);
	}

	return 0;
}
