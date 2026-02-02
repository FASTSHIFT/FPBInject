/* Mock dirent.h for NuttX build test */
#ifndef _MOCK_DIRENT_H
#define _MOCK_DIRENT_H

#include <sys/types.h>

/* Directory entry types */
#define DT_UNKNOWN 0
#define DT_REG     1
#define DT_DIR     2

/* Mock DIR type */
typedef struct {
    int dummy;
} DIR;

/* Directory entry structure */
struct dirent {
    char d_name[256];
    unsigned char d_type;
};

/* Mock function declarations */
static inline DIR* opendir(const char* name) { (void)name; return (DIR*)0; }
static inline struct dirent* readdir(DIR* dirp) { (void)dirp; return (struct dirent*)0; }
static inline int closedir(DIR* dirp) { (void)dirp; return 0; }

/* Enable d_type field */
#define _DIRENT_HAVE_D_TYPE 1

#endif /* _MOCK_DIRENT_H */
