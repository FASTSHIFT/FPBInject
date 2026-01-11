/**
 * @file   test.h
 * @brief  FPB injection functionality test module header
 */

#ifndef __TEST_H
#define __TEST_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Test result structure
 */
typedef struct {
    const char* test_name;
    const char* message;
    uint32_t value;
    bool passed;
} fpb_test_result_t;

/**
 * @brief Run all FPB tests
 * @param results Test result array (at least 10 elements)
 * @param num_tests Returns actual number of tests
 */
void fpb_run_all_tests(fpb_test_result_t* results, uint8_t* num_tests);

/**
 * @brief Get test summary
 */
void fpb_get_test_summary(fpb_test_result_t* results, uint8_t num_tests, uint8_t* passed, uint8_t* failed);

/* Individual test functions */
fpb_test_result_t fpb_test_init(void);
fpb_test_result_t fpb_test_basic_redirect(void);
fpb_test_result_t fpb_test_parameter_redirect(void);
fpb_test_result_t fpb_test_void_redirect(void);
fpb_test_result_t fpb_test_multi_patch(void);

/**
 * @brief Run FPB tests (called from main)
 */
void test_run(void);

#ifdef __cplusplus
}
#endif

#endif /* __TEST_H */
