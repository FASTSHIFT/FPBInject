/*
 * C++ test fixture for ELF symbol pipeline testing.
 *
 * Designed to produce C++-specific symbol types for nm + GDB analysis:
 *   - Namespaced symbols
 *   - Class with methods, static members, vtable
 *   - Template functions and classes
 *   - Constructor / destructor
 *   - Operator overloads
 *   - Mangled names (_Z...)
 *   - Guard variables (_ZGV...)
 *   - Virtual functions (vtable _ZTV..., typeinfo _ZTI...)
 *   - Inline functions
 *   - Enum class
 *
 * Build: see build_test_elf.sh (arm-none-eabi-g++)
 */

#include <stdint.h>
#include <stddef.h>

/* ── Namespace ───────────────────────────────────────────── */

namespace HAL {

volatile uint32_t gpio_state = 0;

void GPIO_Init(uint32_t pin, uint32_t mode) {
    gpio_state = (pin << 16) | mode;
}

uint32_t GPIO_Read(uint32_t pin) {
    return gpio_state & 0xFFFF;
}

namespace Detail {
    static volatile uint32_t internal_counter = 0;

    void increment() {
        internal_counter++;
    }
} // namespace Detail

} // namespace HAL

/* ── Enum class ──────────────────────────────────────────── */

enum class Color : uint8_t {
    Red = 0,
    Green = 1,
    Blue = 2,
};

/* ── Simple class (no virtual) ───────────────────────────── */

class Point3D {
public:
    int32_t x, y, z;

    Point3D() : x(0), y(0), z(0) {}
    Point3D(int32_t ax, int32_t ay, int32_t az) : x(ax), y(ay), z(az) {}

    int32_t dot(const Point3D& other) const {
        return x * other.x + y * other.y + z * other.z;
    }

    Point3D operator+(const Point3D& rhs) const {
        return Point3D(x + rhs.x, y + rhs.y, z + rhs.z);
    }

    bool operator==(const Point3D& rhs) const {
        return x == rhs.x && y == rhs.y && z == rhs.z;
    }

    static Point3D origin() {
        return Point3D(0, 0, 0);
    }

    static uint32_t instance_count;
};

uint32_t Point3D::instance_count = 0;

/* ── Class with virtual functions (produces vtable/typeinfo) ─ */

class DeviceBase {
public:
    uint32_t id;

    DeviceBase(uint32_t dev_id) : id(dev_id) {}
    virtual ~DeviceBase() {}

    virtual void init() = 0;
    virtual uint32_t read() = 0;
    virtual void write(uint32_t val) = 0;

    uint32_t get_id() const { return id; }
};

class SensorDevice : public DeviceBase {
public:
    volatile uint32_t value;
    volatile uint32_t config;

    SensorDevice(uint32_t dev_id) : DeviceBase(dev_id), value(0), config(0) {}
    ~SensorDevice() override {}

    void init() override {
        config = 0x01;
    }

    uint32_t read() override {
        return value;
    }

    void write(uint32_t val) override {
        value = val;
    }
};

/* ── Template class ──────────────────────────────────────── */

template <typename T, uint32_t N>
class RingBuffer {
public:
    T data[N];
    volatile uint32_t head;
    volatile uint32_t tail;

    RingBuffer() : head(0), tail(0) {
        for (uint32_t i = 0; i < N; i++) {
            data[i] = T();
        }
    }

    bool push(const T& val) {
        uint32_t next = (head + 1) % N;
        if (next == tail) return false;
        data[head] = val;
        head = next;
        return true;
    }

    bool pop(T& out) {
        if (head == tail) return false;
        out = data[tail];
        tail = (tail + 1) % N;
        return true;
    }

    uint32_t size() const {
        return (head >= tail) ? (head - tail) : (N - tail + head);
    }
};

/* ── Template function ───────────────────────────────────── */

template <typename T>
T clamp(T val, T lo, T hi) {
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

/* ── Global C++ objects ──────────────────────────────────── */

Point3D g_cpp_point(10, 20, 30);
SensorDevice g_sensor(0x42);
RingBuffer<uint32_t, 8> g_ring_u32;
RingBuffer<uint8_t, 16> g_ring_u8;

/* ── Static local with guard variable ────────────────────── */

SensorDevice& get_singleton() {
    static SensorDevice instance(0xFF);
    return instance;
}

/* ── Const C++ data ──────────────────────────────────────── */

const Point3D g_cpp_const_point(1, 2, 3);

/* POD const (goes to .rodata without constructor) */
struct CppConfig {
    uint32_t baud;
    uint8_t  parity;
    uint8_t  stop_bits;
};

const volatile CppConfig g_cpp_config = { 115200, 0, 1 };

/* ── Bare-metal stubs (no libc) ──────────────────────────── */

void *__dso_handle = nullptr;

extern "C" {
    int __cxa_atexit(void (*)(void*), void*, void*) { return 0; }
    int __aeabi_atexit(void*, void (*)(void*), void*) { return 0; }
    int __cxa_guard_acquire(int*) { return 1; }
    void __cxa_guard_release(int*) {}
    void __cxa_pure_virtual() { while(1); }
}

void operator delete(void*, unsigned int) noexcept {}
void operator delete(void*) noexcept {}

extern "C" {
    /* Prevent linker from discarding symbols — called from _start */
    void cpp_test_main();
}

void cpp_test_main() {
    /* Namespace */
    HAL::GPIO_Init(1, 2);
    volatile uint32_t r = HAL::GPIO_Read(1);
    HAL::Detail::increment();

    /* Point3D methods */
    Point3D a(1, 2, 3);
    Point3D b(4, 5, 6);
    volatile int32_t d = a.dot(b);
    Point3D c = a + b;
    volatile bool eq = (a == b);
    Point3D o = Point3D::origin();
    Point3D::instance_count++;

    /* Virtual dispatch */
    g_sensor.init();
    g_sensor.write(123);
    volatile uint32_t sv = g_sensor.read();
    volatile uint32_t sid = g_sensor.get_id();

    /* Template instantiations */
    g_ring_u32.push(42);
    uint32_t v32 = 0;
    g_ring_u32.pop(v32);
    volatile uint32_t sz32 = g_ring_u32.size();

    g_ring_u8.push(7);
    uint8_t v8 = 0;
    g_ring_u8.pop(v8);

    /* Template function */
    volatile int32_t cv = clamp<int32_t>(50, 0, 100);
    volatile uint8_t cu = clamp<uint8_t>(200, 0, 128);

    /* Singleton with guard variable */
    SensorDevice& s = get_singleton();
    s.write(0xAA);

    /* Const C++ data access */
    volatile uint32_t baud = g_cpp_config.baud;
    volatile int32_t cpx = g_cpp_const_point.x;

    (void)r; (void)d; (void)eq; (void)sv; (void)sid;
    (void)sz32; (void)cv; (void)cu; (void)v32; (void)v8;
    (void)baud; (void)cpx;
}

/* ── Entry point ─────────────────────────────────────────── */

extern "C" void _start() {
    cpp_test_main();
    while (1) {}
}
