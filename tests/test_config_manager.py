"""
配置管理器测试
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from src.utils.config_manager import ConfigManager


class TestConfigManager:
    """配置管理器测试类"""

    def setup_method(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(self.temp_dir)

    def teardown_method(self):
        """测试后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_default_config(self):
        """测试默认配置加载"""
        config = self.config_manager.load_config("test_config.yaml")

        # 验证基本结构
        assert "robot" in config
        assert "communication" in config
        assert "control" in config

        # 验证默认值
        assert config["robot"]["name"] == "EvoBot"
        assert config["robot"]["dof"] == 10
        assert config["control"]["frequency"] == 200

    def test_save_and_load_config(self):
        """测试配置保存和加载"""
        # 创建完整的测试配置
        test_config = {
            "robot": {"name": "TestBot", "dof": 10},
            "communication": {"serial": {"port": "COM1", "baudrate": 1000000}},
            "control": {"frequency": 100},
            "trajectory": {
                "default_max_velocity": 500,
                "default_max_acceleration": 1000,
            },
            "safety": {"enable_soft_limits": True},
            "logging": {"enable": True, "level": "INFO"},
            "ui": {"theme": "light"},
        }

        # 保存配置
        success = self.config_manager.save_config(test_config, "test_save.yaml")
        assert success

        # 加载配置
        loaded_config = self.config_manager.load_config("test_save.yaml")
        assert loaded_config["robot"]["name"] == "TestBot"
        assert loaded_config["control"]["frequency"] == 100

    def test_get_config_value(self):
        """测试获取配置值"""
        config = self.config_manager.load_config()

        # 测试简单键
        robot_name = self.config_manager.get_config_value("robot.name")
        assert robot_name == "EvoBot"

        # 测试嵌套键
        baudrate = self.config_manager.get_config_value("communication.serial.baudrate")
        assert baudrate == 1000000

        # 测试不存在的键
        invalid_value = self.config_manager.get_config_value(
            "invalid.key", default="default"
        )
        assert invalid_value == "default"

    def test_set_config_value(self):
        """测试设置配置值"""
        self.config_manager.load_config()

        # 设置值
        success = self.config_manager.set_config_value("robot.name", "NewBot")
        assert success

        # 验证值已更改
        new_name = self.config_manager.get_config_value("robot.name")
        assert new_name == "NewBot"

    def test_config_validation(self):
        """测试配置验证"""
        # 测试无效配置
        invalid_config = {
            "robot": {"dof": 5},  # 错误的自由度
            "communication": {"serial": {"baudrate": 100}},  # 错误的波特率
            "control": {"frequency": 5000},  # 错误的频率
        }

        with pytest.raises(ValueError):
            self.config_manager._validate_config(invalid_config)
