/* Mock sys/stat.h for NuttX build test */
#ifndef _MOCK_SYS_STAT_H
#define _MOCK_SYS_STAT_H

/* For host testing, include the real system sys/stat.h first */
#ifdef FPB_HOST_TESTING
#include_next <sys/stat.h>
#else

#include <sys/types.h>
#include <time.h>

/* File type macros */
#define S_IFMT   0170000
#define S_IFDIR  0040000
#define S_IFREG  0100000

#define S_ISDIR(m)  (((m) & S_IFMT) == S_IFDIR)
#define S_ISREG(m)  (((m) & S_IFMT) == S_IFREG)

/* Mock stat structure */
struct stat {
    mode_t st_mode;
    off_t st_size;
    time_t st_mtime;
};

/* Mock function declarations */
static inline int stat(const char* path, struct stat* buf) {
    (void)path;
    (void)buf;
    return 0;
}

static inline int mkdir(const char* path, mode_t mode) {
    (void)path;
    (void)mode;
    return 0;
}

#endif /* FPB_HOST_TESTING */

#endif /* _MOCK_SYS_STAT_H */
