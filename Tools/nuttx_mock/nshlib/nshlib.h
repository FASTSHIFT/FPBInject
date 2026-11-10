/* Mock nshlib/nshlib.h for the host build of the NuttX port tests */
#ifndef _MOCK_NSHLIB_H
#define _MOCK_NSHLIB_H

/* Shell entry point spawned by the exec back-end; only its address is used */
int nsh_system(int argc, char* argv[]);

#endif /* _MOCK_NSHLIB_H */
