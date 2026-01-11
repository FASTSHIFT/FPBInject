/**
  ******************************************************************************
  * @file    stm32f10x_conf.h 
  * @brief   Library configuration file for STM32F10x Standard Peripheral Library
  * @note    Modified for GCC toolchain
  ******************************************************************************
  */

#ifndef __STM32F10x_CONF_H
#define __STM32F10x_CONF_H

/* Includes ------------------------------------------------------------------*/
#include "stm32f10x_adc.h"
#include "stm32f10x_bkp.h"
// #include "stm32f10x_can.h"
// #include "stm32f10x_cec.h"
// #include "stm32f10x_crc.h"
// #include "stm32f10x_dac.h"
// #include "stm32f10x_dbgmcu.h"
#include "stm32f10x_dma.h"
#include "stm32f10x_exti.h"
#include "stm32f10x_flash.h"
// #include "stm32f10x_fsmc.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_i2c.h"
#include "stm32f10x_iwdg.h"
#include "stm32f10x_pwr.h"
#include "stm32f10x_rcc.h"
// #include "stm32f10x_rtc.h"
// #include "stm32f10x_sdio.h"
#include "stm32f10x_spi.h"
#include "stm32f10x_tim.h"
#include "stm32f10x_usart.h"
// #include "stm32f10x_wwdg.h"
#include "misc.h"

/* Exported macro ------------------------------------------------------------*/
#ifdef  USE_FULL_ASSERT
  #define assert_param(expr) ((expr) ? (void)0 : assert_failed((uint8_t *)__FILE__, __LINE__))
  void assert_failed(uint8_t* file, uint32_t line);
#else
  #define assert_param(expr) ((void)0)
#endif

#endif /* __STM32F10x_CONF_H */
