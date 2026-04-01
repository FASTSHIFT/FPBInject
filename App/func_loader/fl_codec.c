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
 * @file   fl_codec.c
 * @brief  CRC-16 and Base64 codec implementation
 */

#include "fl_codec.h"

/* clang-format off */
static const uint16_t s_crc16_table[256] = {
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD,
    0xE1CE, 0xF1EF, 0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A,
    0xD3BD, 0xC39C, 0xF3FF, 0xE3DE, 0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B,
    0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D, 0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC, 0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861,
    0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B, 0x5AF5, 0x4AD4, 0x7AB7, 0x6A96,
    0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A, 0x6CA6, 0x7C87,
    0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A,
    0x9F59, 0x8F78, 0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3,
    0x5004, 0x4025, 0x7046, 0x6067, 0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290,
    0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256, 0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405, 0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E,
    0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634, 0xD94C, 0xC96D, 0xF90E, 0xE92F,
    0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3, 0xCB7D, 0xDB5C,
    0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83,
    0x1CE0, 0x0CC1, 0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74,
    0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
};
/* clang-format on */

uint16_t fl_crc16_base(uint16_t crc, const void* data, size_t len) {
    const uint8_t* ptr = data;
    while (len--) {
        crc = (crc << 8) ^ s_crc16_table[(crc >> 8) ^ *ptr++];
    }
    return crc;
}

/* clang-format off */
static const uint8_t s_b64_dec[128] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, /* 0-15 */
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, /* 16-31 */
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62,  255, 255, 255, 63,  /* 32-47: +,/ */
    52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  255, 255, 255, 64,  255, 255, /* 48-63: 0-9,= */
    255, 0,   1,   2,   3,   4,   5,   6,   7,   8,   9,   10,  11,  12,  13,  14,  /* 64-79: A-O */
    15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  255, 255, 255, 255, 255, /* 80-95: P-Z */
    255, 26,  27,  28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,  40,  /* 96-111: a-o */
    41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  255, 255, 255, 255, 255, /* 112-127: p-z */
};

static const char s_b64_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
/* clang-format on */

ssize_t fl_base64_decode(const char* b64, uint8_t* out, size_t max) {
    if (!b64 || !out) {
        return -1;
    }

    size_t b64_len = strlen(b64);
    if (b64_len == 0 || b64_len % 4 != 0) {
        return -1;
    }

    size_t out_len = (b64_len / 4) * 3;
    /* Adjust for padding */
    if (b64[b64_len - 1] == '=') {
        out_len--;
    }
    if (b64_len >= 2 && b64[b64_len - 2] == '=') {
        out_len--;
    }

    if (out_len > max) {
        return -1;
    }

    size_t i = 0, j = 0;
    while (i < b64_len) {
        uint8_t c0 = (uint8_t)b64[i];
        uint8_t c1 = (uint8_t)b64[i + 1];
        uint8_t c2 = (uint8_t)b64[i + 2];
        uint8_t c3 = (uint8_t)b64[i + 3];

        if (c0 >= 128 || c1 >= 128 || c2 >= 128 || c3 >= 128) {
            return -1;
        }

        uint8_t v0 = s_b64_dec[c0];
        uint8_t v1 = s_b64_dec[c1];
        uint8_t v2 = s_b64_dec[c2];
        uint8_t v3 = s_b64_dec[c3];

        if (v0 == 255 || v1 == 255 || (v2 == 255 && v2 != 64) || (v3 == 255 && v3 != 64)) {
            return -1;
        }

        /* Decode 4 base64 chars -> up to 3 bytes */
        out[j++] = (v0 << 2) | (v1 >> 4);
        if (j < out_len && v2 != 64) {
            out[j++] = ((v1 & 0x0F) << 4) | (v2 >> 2);
            if (j < out_len && v3 != 64) {
                out[j++] = ((v2 & 0x03) << 6) | v3;
            }
        }
        i += 4;
    }

    return (ssize_t)out_len;
}

ssize_t fl_base64_encode(const uint8_t* data, size_t len, char* out, size_t max) {
    if (!data || !out || max == 0) {
        return -1;
    }

    size_t out_len = ((len + 2) / 3) * 4;
    if (out_len + 1 > max) {
        return -1;
    }

    size_t j = 0;
    for (size_t i = 0; i < len; i += 3) {
        uint8_t b0 = data[i];
        uint8_t b1 = (i + 1 < len) ? data[i + 1] : 0;
        uint8_t b2 = (i + 2 < len) ? data[i + 2] : 0;

        out[j++] = s_b64_enc[b0 >> 2];
        out[j++] = s_b64_enc[((b0 & 0x03) << 4) | (b1 >> 4)];
        out[j++] = (i + 1 < len) ? s_b64_enc[((b1 & 0x0F) << 2) | (b2 >> 6)] : '=';
        out[j++] = (i + 2 < len) ? s_b64_enc[b2 & 0x3F] : '=';
    }
    out[j] = '\0';

    return (ssize_t)j;
}
