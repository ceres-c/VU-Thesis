#include "pmbus_inject_glitch_fw.h"

#define TPS_VCORE_REG TPS_REG_BUCK2CTRL

volatile static i2c_sniff_data_t i2c_sniff = {.reg_address = 0, .reg_address_written = false, .value = 0};
volatile static glitch_t glitch = {.ext_offset = 0, .width = 0, .reg_value = 0};

int main()
{
	// TODO maybe we can actually execute from cache? Idk check if we have consistent timings
	// // Disable eXecute In Place cache: we mostly care about consistenct, not speed right now
	// hw_clear_bits(&xip_ctrl_hw->ctrl, XIP_CTRL_EN_BITS);

	stdio_init_all();
	stdio_set_translate_crlf(&stdio_usb, false);
	init_pins();
	i2c_init(pmbus_master_i2c, 1000000); // 1MHz
	i2c_init(pmbus_slave_i2c, 1000000); // 1MHz
	// configure I2C0 for slave mode
	i2c_slave_init(pmbus_slave_i2c, PMBUS_PMIC_ADDRESS, &i2c_slave_recv_irq);

	char cmd = 0;
	while (1) {
		cmd = getchar();
		switch (cmd) {
		case CMD_ARM:
			// Enable GPIO irq on core1 so that we are free to do other things here (i2c sniff irq, usb)
			multicore_reset_core1();
			multicore_launch_core1(glitch_gpio_trig_enable);
			putchar(RESP_OK);
			break;

		case CMD_DISARM:
			// Disable GPIO irq on core1
			multicore_reset_core1();
			multicore_launch_core1(glitch_gpio_trig_disable);
			putchar(RESP_OK);
			break;

		case CMD_EXT_OFFSET:
			uint32_t new_offset;
			fread(&new_offset, sizeof(uint32_t), 1, stdin);
			glitch.ext_offset = new_offset; // fread is not volatile-safe
			putchar(RESP_OK);

		case CMD_SET_GLITCH_WIDTH:
			uint32_t new_width;
			fread(&new_width, sizeof(uint32_t), 1, stdin);
			glitch.width = new_width; // fread is not volatile-safe
			putchar(RESP_OK);
			break;

		case CMD_SET_GLITCH_VOLTAGE:
			// Set the target VCORE glitch voltage
			uint8_t new_value;
			fread(&new_value, sizeof(uint8_t), 1, stdin);
			if (new_value > TPS_VCORE_MAX) {
				putchar(RESP_KO);
				puts("[!] Value risks frying the CPU. Ignoring");
				break;
			}
			glitch.reg_value = new_value;
			putchar(RESP_OK);
			break;

		case CMD_GET_I2C_VCORE:
			uint8_t i2c_sniff_val = i2c_sniff.value;
			putchar(i2c_sniff_val);
			break;

		case CMD_TRIGGER_USB:
			// Force a trigger
			do_glitch();
			break;

		case CMD_PING:
			putchar(RESP_PONG);
			break;

		default:
			putchar(RESP_KO);
			break;
		}
	}

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

static void __not_in_flash_func(i2c_slave_recv_irq)(i2c_inst_t *i2c, i2c_slave_event_t event) {
	/**
	 * @brief I2C slave receive IRQ handler. Sniffs the I2C bus for the PMIC register writes
	 * and stores the value in a global variable
	 *
	 * @param i2c The I2C instance
	 * @param event The event that triggered the IRQ
	 * 
	*/
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
	case I2C_SLAVE_FINISH: // master has signalled Stop / Restart
		i2c_sniff.reg_address_written = false;
		break;
	default:
		break;
	}
}

void glitch_gpio_trig_enable() {
	gpio_set_irq_enabled_with_callback(TRIGGER_IN_PIN, GPIO_IRQ_EDGE_RISE , true, &do_glitch);
}
void glitch_gpio_trig_disable() {
	gpio_set_irq_enabled(TRIGGER_IN_PIN, GPIO_IRQ_EDGE_RISE, false);
}

void __not_in_flash_func(do_glitch)() {
	/**
	 * @brief Perform the glitch (can be registered as a GPIO irq callback).
	 * Temporarily disables interrupts when running the time-critical part
	 *
	 * This function runs on core1 when triggered by a GPIO irq, conversely
	 * when a trigger is forced with the serial command `T`, it runs on core0.
	*/

	uint32_t ints = save_and_disable_interrupts();
	uint8_t glitch_val = glitch.reg_value;
	uint8_t restore_val = i2c_sniff.value;
	if (glitch_val > TPS_VCORE_MAX) { // Makes things slower, but safer
		putchar(RESP_GLITCH_FAIL);
		puts("Glitch value is unsafe. Ignoring");
		return;
	}
	if (restore_val > TPS_VCORE_MAX) {
		putchar(RESP_GLITCH_FAIL);
		puts("Sniffed value is unsafe. Ignoring");
		return;
	}
	uint8_t pmbus_cmd_glitch[TPS_WRITE_REG_CMD_LEN] = {TPS_VCORE_REG, glitch_val};
	uint8_t pmbus_cmd_restore[TPS_WRITE_REG_CMD_LEN] = {TPS_VCORE_REG, restore_val};
	busy_wait_us_32(glitch.ext_offset);
	gpio_put(PMBUS_MASTER_OE_PIN, 1);
	int write_glitch_res = i2c_write_timeout_us(pmbus_master_i2c, PMBUS_PMIC_ADDRESS, pmbus_cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 1000);
	busy_wait_us_32(glitch.width);
	int write_restore_res = i2c_write_timeout_us(pmbus_master_i2c, PMBUS_PMIC_ADDRESS, pmbus_cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 1000);
	gpio_put(PMBUS_MASTER_OE_PIN, 0);
	restore_interrupts(ints);

	if (write_glitch_res == PICO_ERROR_GENERIC | write_glitch_res == PICO_ERROR_TIMEOUT) {
		putchar(RESP_GLITCH_FAIL);
		printf("Error writing glitch voltage to I2C\n");
	}
	if (write_restore_res == PICO_ERROR_GENERIC | write_restore_res == PICO_ERROR_TIMEOUT) {
		putchar(RESP_GLITCH_FAIL);
		printf("Error restoring voltage to I2C\n");
	}
	putchar(RESP_GLITCH_SUCCESS);
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
