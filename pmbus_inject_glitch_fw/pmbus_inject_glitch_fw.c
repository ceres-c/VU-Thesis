#include "pmbus_inject_glitch_fw.h"

static void init_pins() {
	gpio_pull_down(PMBUS_MASTER_OE_PIN);
	gpio_pull_up(PMBUS_MASTER_SDA_PIN);
	gpio_pull_up(PMBUS_MASTER_SCL_PIN);

	gpio_set_function(PMBUS_MASTER_OE_PIN, GPIO_FUNC_SIO);
	gpio_set_function(PMBUS_MASTER_SDA_PIN, GPIO_FUNC_I2C);
	gpio_set_function(PMBUS_MASTER_SCL_PIN, GPIO_FUNC_I2C);

	gpio_set_dir(PMBUS_MASTER_OE_PIN, GPIO_OUT);
}

int main()
{
	// Disable eXecute In Place cache: we mostly care about consistenct, not speed right now
	hw_clear_bits(&xip_ctrl_hw->ctrl, XIP_CTRL_EN_BITS); // TODO maybe we can execute from cache? idk
	
	stdio_init_all();
	stdio_set_translate_crlf(&stdio_usb, false);
	init_pins();
	i2c_init(pmbus_i2c, 1000000); // 1MHz

	uint8_t pmbus_cmd[2] = {0x00, 0x00};
	pmbus_cmd[0] = TPS_CMD_BUCK2CTRL;
	pmbus_cmd[1] = 0x00; // 0V

	while (1) {
		puts("Press any key to continue...");
		getchar();
		gpio_put(PMBUS_MASTER_OE_PIN, 1);
		int write_res = i2c_write_timeout_us(pmbus_i2c, TPS_PMBUS_ADDRESS, pmbus_cmd, sizeof(pmbus_cmd) / sizeof(pmbus_cmd[0]), false, 1000);
		gpio_put(PMBUS_MASTER_OE_PIN, 0);
		if (write_res == PICO_ERROR_GENERIC | write_res == PICO_ERROR_TIMEOUT) {
			printf("Error writing to I2C\n");
		} else {
			printf("Written to I2C\n");
		}
	}

	return 0;
}
