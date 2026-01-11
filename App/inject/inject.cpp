#include <Arduino.h>

__attribute__((used, section(".text.inject"))) void inject_digitalWrite(uint8_t pin, uint8_t value) {
    Serial.printf("Injected: pin=%d val=%d ms=%d\n", pin, value, (int)millis());
    value ? digitalWrite_HIGH(pin) : digitalWrite_LOW(pin);
}

__attribute__((used, section(".text.inject"))) void inject_no_args(void)
{
    Serial.printf("Injected: no args, ms=%d\n", (int)millis());
}
