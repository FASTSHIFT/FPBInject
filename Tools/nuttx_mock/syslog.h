/*
 * Mock syslog.h for build testing
 */

#ifndef __SYSLOG_H
#define __SYSLOG_H

#include <stdio.h>
#include <stdarg.h>

/* Log levels */
#define LOG_EMERG   0
#define LOG_ALERT   1
#define LOG_CRIT    2
#define LOG_ERR     3
#define LOG_WARNING 4
#define LOG_NOTICE  5
#define LOG_INFO    6
#define LOG_DEBUG   7

/* Mock syslog function */
static inline void syslog(int priority, const char* fmt, ...)
{
    (void)priority;
    va_list args;
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
}

#endif /* __SYSLOG_H */
