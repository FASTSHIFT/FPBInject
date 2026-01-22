/*
 * Mock NuttX config.h for build testing
 */

#ifndef __NUTTX_CONFIG_H
#define __NUTTX_CONFIG_H

/* Enable debug features for testing */
#define CONFIG_ARCH_HAVE_DEBUG 1

/* Enable FPB inject testing */
#define CONFIG_FPBINJECT_FL 1

#endif /* __NUTTX_CONFIG_H */
