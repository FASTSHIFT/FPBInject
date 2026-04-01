/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   fl_codec.h
 * @brief  CRC-16 and Base64 codec for func_loader
 */

#ifndef FL_CODEC_H
#define FL_CODEC_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/**
 * @brief  CRC-16-CCITT incremental calculation
 * @param  crc  Initial CRC value (0xFFFF for first call)
 * @param  data Data buffer
 * @param  len  Data length
 * @return Updated CRC value
 */
uint16_t fl_crc16_base(uint16_t crc, const void* data, size_t len);

static inline uint16_t fl_crc16(const void* data, size_t len) {
    return fl_crc16_base(0xFFFF, data, len);
}

static inline uint16_t fl_crc16_str(const char* str) {
    return fl_crc16_base(0xFFFF, str, strlen(str));
}

static inline uint16_t fl_crc16_base_str(uint16_t crc, const char* str) {
    return fl_crc16_base(crc, str, strlen(str));
}

/**
 * @brief  Decode Base64 string to bytes
 * @param  b64 Base64 input string
 * @param  out Output buffer
 * @param  max Output buffer size
 * @return Number of decoded bytes, or -1 on error
 */
int fl_base64_decode(const char* b64, uint8_t* out, size_t max);

/**
 * @brief  Encode bytes to Base64 string
 * @param  data Input data
 * @param  len  Input length
 * @param  out  Output string buffer
 * @param  max  Output buffer size
 * @return Number of Base64 characters written, or -1 on error
 */
int fl_base64_encode(const uint8_t* data, size_t len, char* out, size_t max);

#ifdef __cplusplus
}
#endif

#endif /* FL_CODEC_H */
