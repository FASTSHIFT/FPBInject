#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coverage Analyzer Tool
分析代码覆盖率详情，列出具体的未覆盖行号。
"""

import sys
import os
import unittest
import coverage

# 添加父目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)


def main():
    print("正在运行测试并分析覆盖率，请稍候...")

    # 初始化覆盖率统计
    cov = coverage.Coverage(
        source=[PARENT_DIR],
        omit=[
            "*/test/*",
            "*/__pycache__/*",
            "*/static/*",
            "*/templates/*",
            "*/venv/*",
            "*/env/*",
        ],
    )
    cov.start()

    # 运行所有测试
    loader = unittest.TestLoader()
    # 屏蔽标准输出以获得清晰的报告
    # stream = open(os.devnull, 'w')
    suite = loader.discover(SCRIPT_DIR, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    cov.stop()
    cov.save()

    print("\n" + "=" * 80)
    print("详细覆盖率报告 (含未覆盖行号)")
    print("=" * 80)

    # show_missing=True 会在报告中显示 Miss 列对应的行号
    cov.report(show_missing=True)

    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
