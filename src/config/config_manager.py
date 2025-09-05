# -*- coding: utf-8 -*-
"""
配置管理模块
实现JSON配置文件的加载、保存和管理
"""

import json
import logging
import os
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.default_config_path = Path(__file__).parent / "default_config.json"
        self._config = {}
        self.load()
    
    def load(self) -> bool:
        """
        加载配置文件
        
        Returns:
            是否加载成功
        """
        try:
            # 首先尝试加载用户配置文件
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                logger.info(f"已加载用户配置文件: {self.config_path}")
            else:
                user_config = {}
                logger.info("用户配置文件不存在，将使用默认配置")
            
            # 加载默认配置
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                default_config = json.load(f)
            
            # 合并配置（用户配置覆盖默认配置）
            self._config = self._merge_config(default_config, user_config)
            
            # 如果用户配置文件不存在，创建一个
            if not self.config_path.exists():
                self.save()
            
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            # 如果加载失败，使用默认配置
            try:
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info("已回退到默认配置")
                return True
            except Exception as e2:
                logger.error(f"加载默认配置也失败: {e2}")
                return False
    
    def save(self) -> bool:
        """
        保存配置文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置文件已保存: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def _merge_config(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归合并配置字典
        
        Args:
            default: 默认配置
            user: 用户配置
            
        Returns:
            合并后的配置
        """
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的嵌套键）
        
        Args:
            key: 配置键，支持 "app.name" 格式
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """
        设置配置值（支持点分隔的嵌套键）
        
        Args:
            key: 配置键，支持 "app.name" 格式
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        # 导航到最后一级的父字典
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config.copy()
    
    @property
    def app_name(self) -> str:
        """应用名称"""
        return self.get('app.name', 'UDP示波器')
    
    @property
    def app_version(self) -> str:
        """应用版本"""
        return self.get('app.version', '1.0.0')
    
    @property
    def refresh_rate(self) -> int:
        """界面刷新率"""
        return self.get('app.refresh_rate', 120)
    
    @property
    def udp_host(self) -> str:
        """UDP监听地址"""
        return self.get('udp.host', 'localhost')
    
    @property
    def udp_port(self) -> int:
        """UDP监听端口"""
        return self.get('udp.port', 8888)
    
    @property
    def target_host(self) -> str:
        """目标主机地址"""
        return self.get('udp.target_host', '192.168.1.100')
    
    @property
    def target_port(self) -> int:
        """目标端口"""
        return self.get('udp.target_port', 8889)
    
    @property
    def opengl_enabled(self) -> bool:
        """是否启用OpenGL"""
        return self.get('display.opengl_enabled', True)
