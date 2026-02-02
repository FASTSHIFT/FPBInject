/* Mock unistd.h for NuttX build test */
#ifndef _MOCK_UNISTD_H
#define _MOCK_UNISTD_H

#include <sys/types.h>

/* Seek whence values */
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

/* Mock function declarations */
static inline int close(int fd) { (void)fd; return 0; }
static inline ssize_t read(int fd, void* buf, size_t count) { (void)fd; (void)buf; (void)count; return -1; }
static inline ssize_t write(int fd, const void* buf, size_t count) { (void)fd; (void)buf; (void)count; return -1; }
static inline off_t lseek(int fd, off_t offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
static inline int fsync(int fd) { (void)fd; return 0; }
static inline int unlink(const char* path) { (void)path; return 0; }
/* Note: rename is declared in stdio.h, so we don't mock it here */

#endif /* _MOCK_UNISTD_H */
