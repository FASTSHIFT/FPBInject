/**
 * @file   syscalls.c
 * @brief  Newlib syscalls for printf redirection to USART1
 */

#include "stm32f10x.h"
#include <sys/stat.h>
#include <errno.h>

#ifndef PRINTF_UART
#define PRINTF_UART USART1
#endif

/**
 * @brief  Send a character to UART (blocking)
 */
static void uart_putc(char c) {
    while (!(PRINTF_UART->SR & USART_FLAG_TXE))
        ;
    PRINTF_UART->DR = (uint8_t)c;
}

/**
 * @brief  _write syscall - redirect stdout/stderr to UART
 */
int _write(int fd, char* ptr, int len) {
    (void)fd;

    for (int i = 0; i < len; i++) {
        if (ptr[i] == '\n') {
            uart_putc('\r');
        }
        uart_putc(ptr[i]);
    }
    return len;
}

/**
 * @brief  _read syscall - read from UART (blocking)
 */
int _read(int fd, char* ptr, int len) {
    (void)fd;

    for (int i = 0; i < len; i++) {
        while (!(PRINTF_UART->SR & USART_FLAG_RXNE))
            ;
        ptr[i] = (char)(PRINTF_UART->DR & 0xFF);

        /* Echo back */
        uart_putc(ptr[i]);

        /* Return on newline */
        if (ptr[i] == '\r' || ptr[i] == '\n') {
            uart_putc('\n');
            return i + 1;
        }
    }
    return len;
}

/* Minimal stubs for newlib */
int _close(int fd) {
    (void)fd;
    return -1;
}

int _lseek(int fd, int ptr, int dir) {
    (void)fd;
    (void)ptr;
    (void)dir;
    return 0;
}

int _fstat(int fd, struct stat* st) {
    (void)fd;
    st->st_mode = S_IFCHR;
    return 0;
}

int _isatty(int fd) {
    (void)fd;
    return 1;
}

void* _sbrk(int incr) {
    extern char _end;
    extern char _heap_end;
    static char* heap_ptr = NULL;

    if (heap_ptr == NULL) {
        heap_ptr = &_end;
    }

    char* prev_heap = heap_ptr;

    if (heap_ptr + incr > &_heap_end) {
        errno = ENOMEM;
        return (void*)-1;
    }

    heap_ptr += incr;
    return prev_heap;
}
