/* Mock fcntl.h for NuttX build test */
#ifndef _MOCK_FCNTL_H
#define _MOCK_FCNTL_H

/* For host testing, include the real system fcntl.h first */
#ifdef FPB_HOST_TESTING
#include_next <fcntl.h>
#else

/* File open flags */
#define O_RDONLY  0x0000
#define O_WRONLY  0x0001
#define O_RDWR    0x0002
#define O_CREAT   0x0100
#define O_TRUNC   0x0200
#define O_APPEND  0x0400

/* Mock function declarations */
static inline int open(const char* path, int flags, ...) {
    (void)path;
    (void)flags;
    return -1;
}

#endif /* FPB_HOST_TESTING */

#endif /* _MOCK_FCNTL_H */
