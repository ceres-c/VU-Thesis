#ifndef _PMBUS_H
#define _PMBUS_H

#define PMBUS_PMIC_ADDRESS			0x5E // Stated in the datasheet and confirmed sniffing the I2C bus

#define TPS_REG_BUCK1CTRL			0x20
#define TPS_REG_BUCK2CTRL			0x21
#define TPS_REG_BUCK3CTRL			0x23
#define TPS_REG_BUCK4CTRL			0x25
#define TPS_REG_BUCK5CTRL			0x26
#define TPS_REG_BUCK6CTRL			0x27
#define TPS_REG_DISCHCNT1			0x40
#define TPS_REG_DISCHCNT2			0x41
#define TPS_REG_DISCHCNT3			0x42
#define TPS_REG_POK_DELAY			0x43
#define TPS_REG_FORCESHUTDN			0x91
#define TPS_REG_BUCK4VID			0x94
#define TPS_REG_BUCK5VID			0x96
#define TPS_REG_BUCK6VID			0x98
#define TPS_REG_LDOA2VID			0x9A
#define TPS_REG_LDOA3VID			0x9B
#define TPS_REG_VR_CTRL1			0x9C
#define TPS_REG_VR_CTRL2			0x9E
#define TPS_REG_VR_CTRL3			0x9F
#define TPS_REG_GPO_CTRL			0xA1
#define TPS_REG_PWR_FAULT_MASK1		0xA2
#define TPS_REG_PWR_FAULT_MASK2		0xA3
#define TPS_REG_DISCHCNT4			0xAD
#define TPS_REG_LDOA1CTRL			0xAE
#define TPS_REG_PG_STATUS1			0xB0
#define TPS_REG_PG_STATUS2			0xB1
#define TPS_REG_PWR_FAULT_STATUS1	0xB2
#define TPS_REG_PWR_FAULT_STATUS2	0xB3
#define TPS_REG_TEMPHOT				0xB5

#define TPS_WRITE_REG_CMD_LEN		2

// These apply to BUCK1, BUCK2, BUCK5, BUCK6 (TPS65094 - Table 6-3)
#define TPS_VCORE_ZERO				0b00000000 // 0V
#define TPS_VCORE_MIN				0b00000001 // 0.5V
#define TPS_VCORE_MIN_V				0.5f
#define TPS_VCORE_MAX				0b1001011 // 1.24V - Do not go above this value to avoid frying the CPU
#define TPS_VCORE_MAX_V				1.24f	  // Value sniffed from the bus when running stress

#endif // _PMBUS_H
