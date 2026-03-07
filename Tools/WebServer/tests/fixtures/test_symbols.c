/*
 * Test fixture for ELF symbol pipeline testing.
 *
 * Designed to produce diverse symbol types for nm + GDB analysis:
 *   - Functions (T/t): global, static, weak
 *   - Variables (D/d/B/b): global, static, BSS, initialized
 *   - Constants (R/r): const data, rodata
 *   - Structs: nested, with padding, unions
 *   - Arrays: fixed-size, const
 *   - Linker symbols: provided via linker script
 *
 * Build: see build_test_elf.sh
 */

#include <stdint.h>
#include <stddef.h>

/* ── Structs ─────────────────────────────────────────────── */

struct Point {
    int32_t x;
    int32_t y;
};

struct Rect {
    struct Point origin;
    struct Point size;
};

struct PaddedStruct {
    uint8_t  a;       /* +0, 1 byte */
    /* 3 bytes padding */
    uint32_t b;       /* +4, 4 bytes */
    uint16_t c;       /* +8, 2 bytes */
    uint8_t  d;       /* +10, 1 byte */
    /* 1 byte padding */
    /* total: 12 bytes */
};

struct Nested {
    struct PaddedStruct inner;
    uint32_t id;
};

union MixedUnion {
    uint32_t as_u32;
    float    as_float;
    uint8_t  as_bytes[4];
};

typedef struct {
    const char *name;
    uint32_t    addr;
    uint8_t     type;
    uint8_t     channel;
} PinMap_t;

/* ── Global variables (.data section — initialized) ────── */

volatile uint32_t g_counter = 42;
int32_t g_signed_var = -100;
struct Point g_point = { .x = 10, .y = 20 };
struct Rect g_rect = { .origin = {0, 0}, .size = {100, 200} };
struct PaddedStruct g_padded = { .a = 1, .b = 0xDEADBEEF, .c = 0x1234, .d = 0xFF };
struct Nested g_nested = { .inner = { 2, 0xCAFE, 3, 4 }, .id = 999 };
union MixedUnion g_union = { .as_u32 = 0x12345678 };

/* ── BSS variables (.bss section — zero-initialized) ───── */

uint32_t g_bss_var;
struct Point g_bss_point;
uint8_t g_bss_array[64];

/* ── Const data (.rodata section) ────────────────────────── */

const uint32_t g_const_value = 0xA5A5A5A5;
const struct Point g_const_point = { .x = 42, .y = 84 };
const char g_const_string[] = "FPBInject Test Fixture";
const uint8_t g_const_table[16] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
};

const PinMap_t g_pin_map[4] = {
    { "PA0", 0x40010800, 0, 0 },
    { "PA1", 0x40010800, 0, 1 },
    { "PB0", 0x40010C00, 1, 0 },
    { "PB1", 0x40010C00, 1, 1 },
};

/* ── Static variables (local linkage) ────────────────────── */

static volatile uint32_t s_static_var = 100;
static volatile const uint32_t s_static_const = 200;
static volatile uint32_t s_bss_static;

/* ── Functions ───────────────────────────────────────────── */

/* Global function (T) */
void global_func(void) {
    g_counter++;
}

/* Function with parameters and return */
int32_t add_values(int32_t a, int32_t b) {
    return a + b;
}

/* Function using struct */
struct Point make_point(int32_t x, int32_t y) {
    struct Point p = { .x = x, .y = y };
    return p;
}

/* Function with local static variable */
uint32_t get_call_count(void) {
    static uint32_t call_count = 0;
    call_count++;
    return call_count;
}

/* Function with array parameter */
uint32_t sum_array(const uint32_t *arr, uint32_t len) {
    uint32_t sum = 0;
    for (uint32_t i = 0; i < len; i++) {
        sum += arr[i];
    }
    return sum;
}

/* Static function (t) */
__attribute__((noinline))
static int32_t static_helper(int32_t val) {
    return val * 2 + s_static_var;
}

/* Weak function (W) — can be overridden */
__attribute__((weak))
void weak_handler(void) {
    g_bss_var = 0;
}

/* Function using union */
float uint_to_float(uint32_t val) {
    union MixedUnion u;
    u.as_u32 = val;
    return u.as_float;
}

/* Function reading const data */
uint32_t read_const_table(uint32_t idx) {
    if (idx >= sizeof(g_const_table))
        return 0;
    return g_const_table[idx];
}

/* Function using nested struct */
uint32_t get_nested_id(const struct Nested *n) {
    return n->id;
}

/* ── Entry point ─────────────────────────────────────────── */

void _start(void) {
    global_func();
    g_point = make_point(1, 2);
    g_signed_var = add_values(10, 20);
    g_bss_var = get_call_count();
    g_bss_var = sum_array(g_const_table, 16);
    g_bss_var = static_helper(5);
    weak_handler();
    g_union.as_float = uint_to_float(0x3F800000);
    g_bss_var = read_const_table(3);
    g_bss_var = get_nested_id(&g_nested);
    s_bss_static = s_static_const;

    while (1) {}
}
