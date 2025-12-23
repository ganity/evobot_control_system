"""
日志系统

功能：
- 基于Loguru的日志管理
- 多级别日志输出
- 日志文件轮转和归档
- 性能监控日志
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
import time
from functools import wraps


class LoggerManager:
    """日志管理器"""

    def __init__(self):
        self.is_initialized = False
        self.log_dir = Path("logs")

    def setup_logger(self, config: Dict[str, Any]) -> None:
        """
        设置日志系统

        Args:
            config: 日志配置
        """
        if self.is_initialized:
            return

        # 移除默认处理器
        logger.remove()

        # 获取配置参数
        log_level = config.get("level", "INFO")
        log_file = config.get("log_file", "logs/robot.log")
        max_file_size = config.get("max_file_size", 10485760)  # 10MB
        backup_count = config.get("backup_count", 5)

        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 控制台输出（彩色）
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>",
            colorize=True,
        )

        # 文件输出（详细格式）
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {process.id} | {message}",
            rotation=max_file_size,
            retention=backup_count,
            compression="zip",
            encoding="utf-8",
        )

        # 错误日志单独文件
        error_log_file = log_path.parent / "error.log"
        logger.add(
            str(error_log_file),
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {process.id} | {message}",
            rotation="1 day",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )

        # 性能日志
        perf_log_file = log_path.parent / "performance.log"
        logger.add(
            str(perf_log_file),
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | PERF | {message}",
            filter=lambda record: "PERF" in record["message"],
            rotation="1 day",
            retention="7 days",
            encoding="utf-8",
        )

        self.is_initialized = True
        logger.info("日志系统初始化完成")
        logger.info(f"日志级别: {log_level}")
        logger.info(f"日志文件: {log_file}")

    def get_logger(self, name: str):
        """
        获取指定名称的日志器

        Args:
            name: 日志器名称

        Returns:
            日志器实例
        """
        return logger.bind(name=name)


# 全局日志管理器
_logger_manager = LoggerManager()


def setup_logger(config: Dict[str, Any]) -> None:
    """
    设置日志系统

    Args:
        config: 日志配置
    """
    _logger_manager.setup_logger(config)


def get_logger(name: str):
    """
    获取日志器

    Args:
        name: 日志器名称

    Returns:
        日志器实例
    """
    return _logger_manager.get_logger(name)


def log_performance(func):
    """
    性能监控装饰器

    Args:
        func: 被装饰的函数

    Returns:
        装饰后的函数
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000  # 毫秒

            logger.debug(f"PERF | {func.__name__} | 执行时间: {execution_time:.2f}ms")

            # 如果执行时间超过阈值，记录警告
            if execution_time > 100:  # 100ms
                logger.warning(
                    f"函数 {func.__name__} 执行时间过长: {execution_time:.2f}ms"
                )

            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000
            logger.error(
                f"PERF | {func.__name__} | 执行失败: {e} | 执行时间: {execution_time:.2f}ms"
            )
            raise

    return wrapper


def log_method_calls(cls):
    """
    类方法调用日志装饰器

    Args:
        cls: 被装饰的类

    Returns:
        装饰后的类
    """
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and not attr_name.startswith("_"):
            setattr(cls, attr_name, log_performance(attr))
    return cls


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            end_time = time.perf_counter()
            execution_time = (end_time - self.start_time) * 1000

            if exc_type is None:
                logger.debug(f"PERF | {self.name} | 执行时间: {execution_time:.2f}ms")
            else:
                logger.error(
                    f"PERF | {self.name} | 执行失败: {exc_val} | 执行时间: {execution_time:.2f}ms"
                )


# 便捷函数
def perf_monitor(name: str) -> PerformanceMonitor:
    """
    创建性能监控上下文管理器

    Args:
        name: 监控名称

    Returns:
        性能监控器
    """
    return PerformanceMonitor(name)
