/**
 * @file   fpb_test.h
 * @brief  FPB注入功能测试模块头文件
 */

#ifndef __FPB_TEST_H
#define __FPB_TEST_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief 测试结果结构
 */
typedef struct {
    const char* test_name;  /* 测试名称 */
    bool passed;            /* 是否通过 */
    const char* message;    /* 结果消息 */
    uint32_t value;         /* 附加值 (用于调试) */
} FPB_TestResult_t;

/**
 * @brief 运行所有FPB测试
 * @param results 测试结果数组 (至少10个元素)
 * @param num_tests 返回实际测试数量
 */
void FPB_RunAllTests(FPB_TestResult_t* results, uint8_t* num_tests);

/**
 * @brief 获取测试摘要
 */
void FPB_GetTestSummary(FPB_TestResult_t* results, uint8_t num_tests,
                        uint8_t* passed, uint8_t* failed);

/* 独立测试函数 */
FPB_TestResult_t FPB_Test_Init(void);
FPB_TestResult_t FPB_Test_BasicRedirect(void);
FPB_TestResult_t FPB_Test_ParameterRedirect(void);
FPB_TestResult_t FPB_Test_VoidRedirect(void);
FPB_TestResult_t FPB_Test_MultiPatch(void);

#ifdef __cplusplus
}
#endif

#endif /* __FPB_TEST_H */
