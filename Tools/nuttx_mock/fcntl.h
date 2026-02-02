/* Mock fcntl.h for NuttX build test */
#ifndef _MOCK_FCNTL_H
#define _MOCK_FCNTL_H

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

#endif /* _MOCK_FCNTL_H */
