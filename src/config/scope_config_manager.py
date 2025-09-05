# -*- coding: utf-8 -*-
"""
示波器专用配置管理模块
简化的配置管理，专门用于示波器进程
"""

import json
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ScopeConfigManager:
    """示波器配置管理器"""
    
    def __init__(self, config_path: str = "config/scope_config.json"):
        """
        初始化示波器配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self._config = {}
        self.load()
    
    def load(self) -> bool:
        """
        加载配置文件
        
        Returns:
            是否加载成功
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"已加载示波器配置文件: {self.config_path}")
                return True
            else:
                logger.error(f"示波器配置文件不存在: {self.config_path}")
                return False
                
        except Exception as e:
            logger.error(f"加载示波器配置文件失败: {e}")
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
            
            logger.info(f"示波器配置文件已保存: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存示波器配置文件失败: {e}")
            return False
    
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
        return self.get('app.name', 'NASA电机控制器示波器')
    
    @property
    def app_version(self) -> str:
        """应用版本"""
        return self.get('app.version', '1.0.0')
    
    @property
    def refresh_rate(self) -> int:
        """界面刷新率"""
        return self.get('app.refresh_rate', 120)
    
    @property
    def storage_bytes(self) -> int:
        """存储大小（字节）"""
        mb = self.get('storage.max_memory_mb', 1024)
        return mb * 1024 * 1024
    
    @property
    def sample_rate(self) -> float:
        """采样率"""
        return self.get('display.sample_rate', 15000.0)
    
    @property
    def auto_roll(self) -> bool:
        """自动滚动"""
        return self.get('display.auto_roll', True)
    
    @property
    def channel_defs(self) -> list:
        """通道定义列表"""
        return self.get('channels', [])

    @property
    def max_points_window(self) -> int:
        """实时模式最大显示点数"""
        return self.get('display.max_points_window', 300000)

    @property
    def max_points_preview(self) -> int:
        """预览模式最大显示点数"""
        return self.get('display.max_points_preview', 100000)

    @property
    def grid_enabled(self) -> bool:
        """是否显示网格"""
        return self.get('display.grid_enabled', True)

    def get_channel_config(self, channel_index: int) -> Dict[str, Any]:
        """
        获取指定通道的配置
        
        Args:
            channel_index: 通道索引
            
        Returns:
            通道配置字典
        """
        channels = self.channel_defs
        if 0 <= channel_index < len(channels):
            return channels[channel_index].copy()
        else:
            # 返回默认通道配置
            return {
                'name': f'CH{channel_index + 1}',
                'enabled': True,
                'color': '#FFFFFF',
                'vertical_div': 1.0,
                'vertical_offset': 0.0,
                'unit': 'V',
                'scale_factor': 1.0,
                'visible': True
            }
    
    def set_channel_config(self, channel_index: int, config: Dict[str, Any]):
        """
        设置指定通道的配置
        
        Args:
            channel_index: 通道索引
            config: 通道配置字典
        """
        channels = self.channel_defs
        if 0 <= channel_index < len(channels):
            # 更新现有通道配置
            channels[channel_index].update(config)
            self.set('channels', channels)
        else:
            logger.warning(f"通道索引超出范围: {channel_index}")
