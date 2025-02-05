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
	uint8_t expected_ints, new_voltage, new_prep_voltage; // Old gcc does not like variable declarations after a label
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
			expected_ints = getchar();
			glitcher_arm(expected_ints);
			break;
		case P_CMD_FORCE:
			busy_wait_us_32(glitch.ext_offset);
			int write_glitch_res = i2c_write_timeout_us(
				I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
			busy_wait_us_32(glitch.width);
			int write_restore_res = i2c_write_timeout_us(
				I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 100);
			if (write_glitch_res != TPS_WRITE_REG_CMD_LEN)
				printf("write_glitch_res: %d\n", write_glitch_res);
			if (write_restore_res != TPS_WRITE_REG_CMD_LEN)
				printf("write_restore_res: %d\n", write_restore_res);
			putchar(P_CMD_RETURN_OK);
			break;
		case P_CMD_SET_VOLTAGE:
			new_voltage = getchar();
			if (new_voltage > TPS_VCORE_MAX) {
				putchar(P_CMD_RETURN_KO);
				puts("[!] Value risks frying the CPU. Ignoring");
				break;
			}
			glitch.cmd_glitch[1] = new_voltage;
			putchar(P_CMD_RETURN_OK);
			break;
		case P_CMD_SET_EXT_OFFST:
			glitch.ext_offset = getu32();
			putchar(P_CMD_RETURN_OK);
			break;
		case P_CMD_SET_WIDTH:
			glitch.width = getu32();
			putchar(P_CMD_RETURN_OK);
			break;
		case P_CMD_SET_PREP_VOLTAGE:
			new_prep_voltage = getchar();
			if (new_prep_voltage > TPS_VCORE_MAX) {
				putchar(P_CMD_RETURN_KO);
				puts("[!] Value risks frying the CPU. Ignoring");
				break;
			}
			glitch.cmd_prep[1] = new_prep_voltage;
			putchar(P_CMD_RETURN_OK);
			break;
		case P_CMD_UART_ECHO:
			uart_echo();
			break;
		case P_CMD_PING:
			putchar(P_CMD_PONG);
			break;
		case P_CMD_TARGET_PING:
			putchar(ping_target(PING_VCORE_STABLE_CHARS));
			break;
		case P_CMD_TARGET_PING_SLOW:
			putchar(ping_target(PING_VCORE_STABLE_CHARS_SLOW));
			break;
		case P_CMD_MEASURE_LOOP_DURATION:
			putu32(measure_loop());
			break;
		case P_CMD_UART_TOGGLE_DEBUG_PIN:
			putchar(uart_debug_pin_toggle());
			break;
		case P_CMD_DEBUG_PULSE:
			gpio_put(PIN_DEBUG, 1);
			busy_wait_us_32(10);
			gpio_put(PIN_DEBUG, 0);
			putchar(P_CMD_RETURN_OK);
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

static void init_pins() {
	gpio_disable_pulls(PIN_PMBUS_SDA);	// Don't add extra pulls, let the CPU handle it
	gpio_disable_pulls(PIN_PMBUS_SCL);
	gpio_pull_down(PIN_UART_OE);

	gpio_set_function(PIN_UART_TX, GPIO_FUNC_UART);
	gpio_set_function(PIN_UART_RX, GPIO_FUNC_UART);
	gpio_set_function(PIN_PMBUS_SDA, GPIO_FUNC_I2C);
	gpio_set_function(PIN_PMBUS_SCL, GPIO_FUNC_I2C);
	gpio_set_function(PIN_UART_OE, GPIO_FUNC_SIO);
	gpio_set_function(PIN_LED, GPIO_FUNC_SIO);
	gpio_set_function(PIN_DEBUG, GPIO_FUNC_SIO); // TODO remove when done debugging

	gpio_put(PIN_UART_OE, 0);
	gpio_put(PIN_LED, 0);

	gpio_set_dir(PIN_UART_OE, GPIO_OUT);
	gpio_set_dir(PIN_LED, GPIO_OUT);
	gpio_set_dir(PIN_DEBUG, GPIO_OUT);
}

int main() {
	// Metadata for picotool
	bi_decl(bi_program_description("PicoCoder: Rasperry Pi Pico microcode glitcher"));
	bi_decl(bi_program_url("https://github.com/ceres-c/VU-Thesis/"));
	bi_decl(bi_3pins_with_names(PIN_UART_TX, "TX", PIN_UART_RX, "RX", PIN_UART_OE, "OE"));
	bi_decl(bi_2pins_with_names(PIN_PMBUS_SDA, "SDA", PIN_PMBUS_SCL, "SCL"));
	bi_decl(bi_1pin_with_name(PIN_LED, "LED"));
	bi_decl(bi_4pins_with_names(PIN_SPI_MISO, "MISO", PIN_SPI_MOSI, "MOSI", PIN_SPI_SCK, "SCK", PIN_SPI_CS, "CS#"));

	stdio_init_all();
	stdio_set_translate_crlf(&stdio_usb, false);
	init_pins();
	target_uart_init();									// UART:	RPi <-> coreboot (115200 baud)
	uint actual_baud = i2c_init(I2C_PMBUS, PMBUS_BAUD);	// PMBus:	CPU <-> PMIC (1 MHz)
	if (actual_baud < (PMBUS_BAUD - 1000) || actual_baud > (PMBUS_BAUD + 1000)) {
		while (1)
			printf("I2C baudrate mismatch: %d. Halting\n", actual_baud);
	}
	serprog_spi_init(&spi, 1000000);					// Serprog:	RPi <-> BIOS flash (1 MHz)

	// Command handling
	while(1) {
		int command = getchar();

		gpio_put(PIN_LED, 1);
		process(&spi, command);
		gpio_put(PIN_LED, 0);
	}

	return 0;
}
