#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPBInject WebServer 测试运行器

支持覆盖率统计和HTML报告生成。

使用方法:
    ./test/run_tests.py              # 运行所有测试
    ./test/run_tests.py -v           # 详细输出
    ./test/run_tests.py --coverage   # 运行测试并生成覆盖率报告
    ./test/run_tests.py --html       # 生成HTML覆盖率报告
    ./test/run_tests.py --target 80  # 设置覆盖率目标为80%
"""

import argparse
import os
import shutil
import sys
import unittest

# 添加父目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

# 默认覆盖率目标
DEFAULT_COVERAGE_TARGET = 80

# 配置文件路径
CONFIG_FILE = os.path.join(PARENT_DIR, "config.json")
CONFIG_BACKUP = os.path.join(PARENT_DIR, "config.json.bak")


def backup_config():
    """备份原始配置文件"""
    if os.path.exists(CONFIG_FILE):
        shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
        return True
    return False


def restore_config():
    """恢复原始配置文件"""
    if os.path.exists(CONFIG_BACKUP):
        shutil.copy2(CONFIG_BACKUP, CONFIG_FILE)
        os.remove(CONFIG_BACKUP)
        return True
    return False


def run_tests(
    verbosity=2,
    with_coverage=False,
    html_report=False,
    coverage_target=DEFAULT_COVERAGE_TARGET,
):
    """
    运行所有测试。

    Args:
        verbosity: 输出详细程度 (0-2)
        with_coverage: 是否启用覆盖率统计
        html_report: 是否生成HTML报告
        coverage_target: 覆盖率目标百分比

    Returns:
        bool: 测试是否全部通过
    """
    # 备份配置文件
    config_backed_up = backup_config()
    if config_backed_up:
        print("📦 配置文件已备份")

    try:
        if with_coverage:
            try:
                import coverage
            except ImportError:
                print("错误: 需要安装 coverage 包")
                print("请运行: pip install coverage")
                sys.exit(1)

            # 创建覆盖率对象
            cov = coverage.Coverage(
                source=[PARENT_DIR],
                omit=[
                    "*/test/*",
                    "*/__pycache__/*",
                    "*/static/*",
                    "*/templates/*",
                ],
            )
            cov.start()

        # 发现并加载测试
        loader = unittest.TestLoader()
        suite = loader.discover(SCRIPT_DIR, pattern="test_*.py")

        # 运行测试
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)

        if with_coverage:
            cov.stop()
            cov.save()

            print("\n" + "=" * 70)
            print("覆盖率报告")
            print("=" * 70)

            # 只调用一次 report()，获取返回的总覆盖率
            total = cov.report()

            if html_report:
                html_dir = os.path.join(SCRIPT_DIR, "htmlcov")
                cov.html_report(directory=html_dir)
                print(f"\nHTML 报告已生成: {html_dir}/index.html")

            # 检查覆盖率是否达标
            if total < coverage_target:
                print(f"\n⚠️  警告: 覆盖率 {total:.1f}% 低于 {coverage_target}% 目标")
            else:
                print(f"\n✅ 覆盖率 {total:.1f}% 达到目标 (≥{coverage_target}%)")

        return result.wasSuccessful()
    finally:
        # 恢复配置文件
        if config_backed_up:
            restore_config()
            print("📦 配置文件已恢复")


def main():
    parser = argparse.ArgumentParser(description="FPBInject WebServer 测试运行器")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--coverage", action="store_true", help="启用覆盖率统计")
    parser.add_argument(
        "--html", action="store_true", help="生成HTML覆盖率报告 (自动启用 --coverage)"
    )
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_COVERAGE_TARGET,
        help=f"覆盖率目标百分比 (默认: {DEFAULT_COVERAGE_TARGET}%%)",
    )

    args = parser.parse_args()

    verbosity = 2 if args.verbose else 1
    with_coverage = args.coverage or args.html

    success = run_tests(
        verbosity=verbosity,
        with_coverage=with_coverage,
        html_report=args.html,
        coverage_target=args.target,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
