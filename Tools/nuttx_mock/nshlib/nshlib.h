/* Mock nshlib/nshlib.h for the host build of the NuttX port tests */
#ifndef _MOCK_NSHLIB_H
#define _MOCK_NSHLIB_H

/* Entry point of the task that system() / the exec back-end spawns: runs
 * "-c <command line>" under the shell. Only its address is ever used. */
int nsh_system(int argc, char* argv[]);

#endif /* _MOCK_NSHLIB_H */
