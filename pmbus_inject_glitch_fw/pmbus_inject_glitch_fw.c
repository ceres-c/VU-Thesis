#include "pmbus_inject_glitch_fw.h"

#define TPS_VCORE_REG TPS_REG_BUCK2CTRL

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


static struct
{
    uint8_t reg_address;
    bool reg_address_written;
	uint8_t value;
} context;

static void i2c_slave_handler(i2c_inst_t *i2c, i2c_slave_event_t event) {
    switch (event) {
    case I2C_SLAVE_RECEIVE: // master has written some data
		uint8_t byte_from_bus = i2c_read_byte_raw(i2c);
        if (!context.reg_address_written && byte_from_bus == TPS_VCORE_REG) {
            // writes always start with the memory address
            context.reg_address = byte_from_bus;
            context.reg_address_written = true;
			break;
        }
		context.value = byte_from_bus;
		break;
    case I2C_SLAVE_REQUEST: // master is requesting data (ignore, actual device will answer)
        break;
    case I2C_SLAVE_FINISH: // master has signalled Stop / Restart
        context.reg_address_written = false;
        break;
    default:
        break;
    }
}

int main()
{
	// Disable eXecute In Place cache: we mostly care about consistenct, not speed right now
	hw_clear_bits(&xip_ctrl_hw->ctrl, XIP_CTRL_EN_BITS); // TODO maybe we can execute from cache? idk
	
	stdio_init_all();
	stdio_set_translate_crlf(&stdio_usb, false);
	init_pins();
	i2c_init(pmbus_master_i2c, 1000000); // 1MHz
	i2c_init(pmbus_slave_i2c, 1000000); // 1MHz
    // configure I2C0 for slave mode
    i2c_slave_init(pmbus_slave_i2c, PMBUS_PMIC_ADDRESS, &i2c_slave_handler);

	uint8_t pmbus_cmd[2] = {0x00, 0x00};
	pmbus_cmd[0] = TPS_VCORE_REG;
	pmbus_cmd[1] = 0x00; // 0V

	while (1) {
		printf("BUCK2 0x%x\n", context.value);
	}
	

	while (1) {
		puts("Press any key to continue...");
		getchar();
		gpio_put(PMBUS_MASTER_OE_PIN, 1);
		int write_res = i2c_write_timeout_us(pmbus_master_i2c, PMBUS_PMIC_ADDRESS, pmbus_cmd, sizeof(pmbus_cmd) / sizeof(pmbus_cmd[0]), false, 1000);
		gpio_put(PMBUS_MASTER_OE_PIN, 0);
		if (write_res == PICO_ERROR_GENERIC | write_res == PICO_ERROR_TIMEOUT) {
			printf("Error writing to I2C\n");
		} else {
			printf("Written to I2C\n");
		}
	}

	return 0;
}
