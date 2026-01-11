/**
 * @file   fpb_test.c
 * @brief  FPB注入功能测试模块
 * 
 * 提供FPB功能的自动化测试，包括:
 * - FPB初始化测试
 * - 函数重定向测试
 * - 指令替换测试
 * - 边界条件测试
 */

#include "fpb_inject.h"
#include "fpb_test.h"
#include <stdio.h>

/*===========================================================================
 * 测试辅助变量
 *===========================================================================*/

static volatile uint32_t test_counter = 0;
static volatile uint32_t original_call_count = 0;
static volatile uint32_t patched_call_count = 0;

/*===========================================================================
 * 测试用函数
 *===========================================================================*/

/* 原始函数A - 返回固定值100 */
__attribute__((noinline))
uint32_t test_func_original_a(void)
{
    original_call_count++;
    return 100;
}

/* 补丁函数A - 返回固定值200 */
__attribute__((noinline))
uint32_t test_func_patched_a(void)
{
    patched_call_count++;
    return 200;
}

/* 原始函数B - 简单计算 */
__attribute__((noinline))
uint32_t test_func_original_b(uint32_t x)
{
    original_call_count++;
    return x * 2;
}

/* 补丁函数B - 不同计算 */
__attribute__((noinline))
uint32_t test_func_patched_b(uint32_t x)
{
    patched_call_count++;
    return x * 3;
}

/* 原始函数C - 无返回值 */
__attribute__((noinline))
void test_func_original_c(void)
{
    original_call_count++;
    test_counter += 10;
}

/* 补丁函数C - 无返回值 */
__attribute__((noinline))
void test_func_patched_c(void)
{
    patched_call_count++;
    test_counter += 100;
}

/*===========================================================================
 * 测试用例
 *===========================================================================*/

/**
 * @brief 测试1: FPB初始化
 */
FPB_TestResult_t FPB_Test_Init(void)
{
    FPB_TestResult_t result = {0};
    result.test_name = "FPB Init";
    
    /* 测试FPB支持检测 */
    if (!FPB_IsSupported())
    {
        result.passed = false;
        result.message = "FPB not supported on this device";
        return result;
    }
    
    /* 初始化FPB */
    int ret = FPB_Init();
    if (ret != 0)
    {
        result.passed = false;
        result.message = "FPB_Init failed";
        return result;
    }
    
    /* 检查状态 */
    const FPB_State_t* state = FPB_GetState();
    if (!state->initialized)
    {
        result.passed = false;
        result.message = "FPB state not initialized";
        return result;
    }
    
    if (state->num_code_comp == 0)
    {
        result.passed = false;
        result.message = "No code comparators available";
        return result;
    }
    
    result.passed = true;
    result.message = "FPB initialized successfully";
    result.value = state->num_code_comp;
    
    return result;
}

/**
 * @brief 测试2: 基本函数重定向
 */
FPB_TestResult_t FPB_Test_BasicRedirect(void)
{
    FPB_TestResult_t result = {0};
    result.test_name = "Basic Function Redirect";
    
    /* 重置计数器 */
    original_call_count = 0;
    patched_call_count = 0;
    
    /* 先测试原始函数 */
    uint32_t ret1 = test_func_original_a();
    if (ret1 != 100)
    {
        result.passed = false;
        result.message = "Original function returned wrong value";
        return result;
    }
    
    if (original_call_count != 1)
    {
        result.passed = false;
        result.message = "Original call count mismatch";
        return result;
    }
    
    /* 设置FPB补丁 */
    int ret = FPB_SetPatch(0, 
                           (uint32_t)test_func_original_a, 
                           (uint32_t)test_func_patched_a);
    if (ret != 0)
    {
        result.passed = false;
        result.message = "FPB_SetPatch failed";
        return result;
    }
    
    /* 再次调用，应该执行补丁函数 */
    uint32_t ret2 = test_func_original_a();
    
    if (ret2 != 200)
    {
        result.passed = false;
        result.message = "Patched function not executed";
        result.value = ret2;
        return result;
    }
    
    if (patched_call_count != 1)
    {
        result.passed = false;
        result.message = "Patched call count mismatch";
        return result;
    }
    
    /* 清除补丁 */
    FPB_ClearPatch(0);
    
    /* 再次调用，应该执行原始函数 */
    uint32_t ret3 = test_func_original_a();
    if (ret3 != 100)
    {
        result.passed = false;
        result.message = "Original function not restored";
        return result;
    }
    
    result.passed = true;
    result.message = "Function redirect works correctly";
    
    return result;
}

/**
 * @brief 测试3: 带参数的函数重定向
 */
FPB_TestResult_t FPB_Test_ParameterRedirect(void)
{
    FPB_TestResult_t result = {0};
    result.test_name = "Parameter Function Redirect";
    
    /* 原始函数测试 */
    uint32_t ret1 = test_func_original_b(10);
    if (ret1 != 20)  /* 10 * 2 = 20 */
    {
        result.passed = false;
        result.message = "Original function calculation wrong";
        return result;
    }
    
    /* 设置补丁 */
    FPB_SetPatch(1, (uint32_t)test_func_original_b, 
                    (uint32_t)test_func_patched_b);
    
    /* 补丁函数测试 */
    uint32_t ret2 = test_func_original_b(10);
    if (ret2 != 30)  /* 10 * 3 = 30 */
    {
        result.passed = false;
        result.message = "Patched function calculation wrong";
        result.value = ret2;
        return result;
    }
    
    /* 清除补丁 */
    FPB_ClearPatch(1);
    
    result.passed = true;
    result.message = "Parameter function redirect works";
    
    return result;
}

/**
 * @brief 测试4: void函数重定向
 */
FPB_TestResult_t FPB_Test_VoidRedirect(void)
{
    FPB_TestResult_t result = {0};
    result.test_name = "Void Function Redirect";
    
    test_counter = 0;
    
    /* 原始函数 */
    test_func_original_c();
    if (test_counter != 10)
    {
        result.passed = false;
        result.message = "Original void function failed";
        return result;
    }
    
    /* 设置补丁 */
    FPB_SetPatch(2, (uint32_t)test_func_original_c, 
                    (uint32_t)test_func_patched_c);
    
    /* 补丁函数 */
    test_func_original_c();
    if (test_counter != 110)  /* 10 + 100 = 110 */
    {
        result.passed = false;
        result.message = "Patched void function failed";
        result.value = test_counter;
        return result;
    }
    
    FPB_ClearPatch(2);
    
    result.passed = true;
    result.message = "Void function redirect works";
    
    return result;
}

/**
 * @brief 测试5: 多补丁同时使用
 */
FPB_TestResult_t FPB_Test_MultiPatch(void)
{
    FPB_TestResult_t result = {0};
    result.test_name = "Multiple Patches";
    
    /* 设置多个补丁 */
    FPB_SetPatch(0, (uint32_t)test_func_original_a, 
                    (uint32_t)test_func_patched_a);
    FPB_SetPatch(1, (uint32_t)test_func_original_b, 
                    (uint32_t)test_func_patched_b);
    
    /* 测试两个函数 */
    uint32_t ret1 = test_func_original_a();
    uint32_t ret2 = test_func_original_b(5);
    
    if (ret1 != 200 || ret2 != 15)
    {
        result.passed = false;
        result.message = "Multi-patch failed";
        return result;
    }
    
    /* 只禁用一个 */
    FPB_EnableComp(0, false);
    
    ret1 = test_func_original_a();
    ret2 = test_func_original_b(5);
    
    if (ret1 != 100 || ret2 != 15)
    {
        result.passed = false;
        result.message = "Selective disable failed";
        return result;
    }
    
    /* 清除所有补丁 */
    FPB_ClearPatch(0);
    FPB_ClearPatch(1);
    
    result.passed = true;
    result.message = "Multiple patches work correctly";
    
    return result;
}

/**
 * @brief 运行所有测试
 */
void FPB_RunAllTests(FPB_TestResult_t* results, uint8_t* num_tests)
{
    uint8_t idx = 0;
    
    /* 初始化FPB */
    FPB_Init();
    
    /* 运行测试 */
    results[idx++] = FPB_Test_Init();
    results[idx++] = FPB_Test_BasicRedirect();
    results[idx++] = FPB_Test_ParameterRedirect();
    results[idx++] = FPB_Test_VoidRedirect();
    results[idx++] = FPB_Test_MultiPatch();
    
    *num_tests = idx;
    
    /* 清理 */
    FPB_DeInit();
}

/**
 * @brief 获取测试结果摘要
 */
void FPB_GetTestSummary(FPB_TestResult_t* results, uint8_t num_tests,
                        uint8_t* passed, uint8_t* failed)
{
    *passed = 0;
    *failed = 0;
    
    for (uint8_t i = 0; i < num_tests; i++)
    {
        if (results[i].passed)
        {
            (*passed)++;
        }
        else
        {
            (*failed)++;
        }
    }
}
