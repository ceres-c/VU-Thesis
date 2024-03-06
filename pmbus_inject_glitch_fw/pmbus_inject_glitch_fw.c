#include "pmbus_inject_glitch_fw.h"

#define TPS_VCORE_REG TPS_REG_BUCK2CTRL

static i2c_sniff_data_t i2c_sniff = {.reg_address = 0, .reg_address_written = false, .value = 0xFF}; // 7th bit is never used
static glitch_t glitch = {.ext_offset = 0, .width = 0};

int main()
{
	// Disable eXecute In Place cache: we mostly care about consistenct, not speed right now
	hw_clear_bits(&xip_ctrl_hw->ctrl, XIP_CTRL_EN_BITS); // TODO maybe we can actually execute from cache? idk

	stdio_init_all();
	stdio_set_translate_crlf(&stdio_usb, false);
	init_pins();
	i2c_init(pmbus_master_i2c, 1000000); // 1MHz
	i2c_init(pmbus_slave_i2c, 1000000); // 1MHz
	// configure I2C0 for slave mode
	i2c_slave_init(pmbus_slave_i2c, PMBUS_PMIC_ADDRESS, &i2c_slave_handler);

	uint8_t pmbus_cmd[2] = {0x00, 0x00};
	pmbus_cmd[0] = TPS_VCORE_REG;

	char cmd = 0;
	while (1) {
		cmd = getchar();
		switch (cmd) {
		case CMD_ARM: // TODO
			// Wait for trigger
			putchar(RESP_KO);
			break;

		case CMD_EXT_OFFSET:
			fread(&glitch.ext_offset, sizeof(uint32_t), 1, stdin);
			putchar(RESP_OK);

		case CMD_WIDTH:
			fread(&glitch.width, sizeof(uint32_t), 1, stdin);
			putchar(RESP_OK);
			break;

		case CMD_VOLTAGE:
			// Set the target VCORE glitch voltage
			uint8_t new_value;
			fread(&new_value, sizeof(uint8_t), 1, stdin);
			if (new_value > TPS_VCORE_MAX) {
				putchar(RESP_KO);
				puts("[!] Value risks frying the CPU. Ignoring");
				break;
			}
			glitch.voltage = new_value;
			putchar(RESP_OK);
			break;

		case CMD_TRIGGER_USB: // TODO
			// Force a trigger
			putchar(RESP_KO);
			break;

		case CMD_PING:
			putchar(RESP_PONG);
			break;

		default:
			putchar(RESP_KO);
			break;
		}
	}

		// uint8_t original_setting = i2c_sniff.value;
		// int32_t glitch_delta_volt = 0, glitch_abs_volt = 0;
		// puts("Give VCORE offset (e.g. +0.1, -0.1) or absolute value (e.g. 0.6): ");
		// scanf("%s", command);
		// if (command[0] == '+') {
		// 	glitch_delta_volt = (int32_t)(atof(command + 1) * 100);
		// } else if (command[0] == '-') {
		// 	glitch_delta_volt = (int32_t)(atof(command + 1) * 100) * -1;
		// } else {
		// 	glitch_abs_volt = (int32_t)(atof(command) * 100);
		// }

		// if (original_setting && 0b10000000) {
		// 	// We do not have any valid value yet
		// 	printf("No valid value has been seen on the i2c bus. Is the glitcher connected?\n");
	// 	// 	continue;
	// 	// }


	// 	gpio_put(PMBUS_MASTER_OE_PIN, 1);
	// 	int write_res = i2c_write_timeout_us(pmbus_master_i2c, PMBUS_PMIC_ADDRESS, pmbus_cmd, sizeof(pmbus_cmd) / sizeof(pmbus_cmd[0]), false, 1000);
	// 	gpio_put(PMBUS_MASTER_OE_PIN, 0);
	// 	if (write_res == PICO_ERROR_GENERIC | write_res == PICO_ERROR_TIMEOUT) {
	// 		printf("Error writing to I2C\n");
	// 	} else {
	// 		printf("Written to I2C\n");
	// 	}
	// }

	return 0;
}

static void init_pins() {
	gpio_pull_down(PMBUS_MASTER_OE_PIN);
	gpio_pull_up(PMBUS_MASTER_SDA_PIN);
	gpio_pull_up(PMBUS_MASTER_SCL_PIN);
	gpio_pull_up(PMBUS_SLAVE_SDA_PIN);
	gpio_pull_up(PMBUS_SLAVE_SCL_PIN);

	gpio_set_function(PMBUS_MASTER_OE_PIN, GPIO_FUNC_SIO);
	gpio_set_function(PMBUS_MASTER_SDA_PIN, GPIO_FUNC_I2C);
	gpio_set_function(PMBUS_MASTER_SCL_PIN, GPIO_FUNC_I2C);
	gpio_set_function(PMBUS_SLAVE_SDA_PIN, GPIO_FUNC_I2C);
	gpio_set_function(PMBUS_SLAVE_SCL_PIN, GPIO_FUNC_I2C);

	gpio_set_dir(PMBUS_MASTER_OE_PIN, GPIO_OUT);
}

static void i2c_slave_handler(i2c_inst_t *i2c, i2c_slave_event_t event) {
	switch (event) {
	case I2C_SLAVE_RECEIVE: // master has written some data
		uint8_t byte_from_bus = i2c_read_byte_raw(i2c);
		if (!i2c_sniff.reg_address_written && byte_from_bus == TPS_VCORE_REG) {
			// writes always start with the memory address
			i2c_sniff.reg_address = byte_from_bus;
			i2c_sniff.reg_address_written = true;
			break;
		}
		i2c_sniff.value = byte_from_bus;
		break;
	case I2C_SLAVE_REQUEST: // master is requesting data (ignore, actual device will answer)
		break;
	case I2C_SLAVE_FINISH: // master has signalled Stop / Restart
		i2c_sniff.reg_address_written = false;
		break;
	default:
		break;
	}
}



// int32_t gen_pmic_cmd(char *cmd_string, uint8_t *pmic_cmd, uint32_t current_value) {
// 	/**
// 	 * @brief Generate a PMIC command from a user-supplied command string
// 	 *
// 	 * @param cmd_string The full command string (starting with 'c')
// 	 * @param pmic_cmd The PMIC command to be filled in
// 	 * @param current_value The current value of the PMIC register (as sniffed from the I2C bus)
// 	 * @return int32_t 0 on success, negative on error
// 	 * 
// 	*/

// 	// "c -0.01" // set VCORE to current_setting-0.01V
// 	// "c +0.01" // set VCORE to current_setting+0.01V
// 	// "c 0.6" // set VCORE to 0.6V

// 	if (current_value && 0b10000000) {
// 		// We do not have any valid value yet
// 		return -1;
// 	}

// 	uint32_t new_value = 0;
// 	if (cmd_string[2] == '+') {
// 		int32_t delta_steps = (int32_t)(atof(cmd_string + 3) * 100);
// 		new_value = current_value + delta_steps;
// 	} else if (cmd_string[2] == '-') {
// 		int32_t delta_steps = (int32_t)(atof(cmd_string + 3) * 100);
// 		new_value = current_value - delta_steps;
// 	} else {
// 		float input = atof(cmd_string + 2);
// 		if (input == 0) {
// 			new_value = 0;
// 		} else if (input < TPS_VCORE_MIN_V || input > TPS_VCORE_MAX_V) {
// 			// Out of range
// 			return -2;
// 		} else {
// 			int32_t abs_value = (int32_t)( (input - TPS_VCORE_MIN_V) * 100) + 1;
// 			new_value = abs_value;
// 		}
// 	}

// 	if (new_value != TPS_VCORE_ZERO && (new_value < TPS_VCORE_MIN || new_value > TPS_VCORE_MAX)) {
// 		// Out of range
// 		return -2;
// 	}

// 	pmic_cmd[0] = TPS_VCORE_REG;
// 	pmic_cmd[1] = new_value;
// 	return 0;
// }
