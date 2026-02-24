"""
QKA策略模块

提供策略开发的抽象基类，定义策略开发的标准接口和事件处理机制。
"""

from abc import ABC, abstractmethod
from typing import Optional
from qka.core.broker import Broker

class Strategy(ABC):
    """
    策略抽象基类

    所有自定义策略都应该继承此类，并实现on_bar方法。

    Attributes:
        broker (Broker): 交易经纪商实例，用于执行交易操作
    """

    def __init__(self, broker: Optional[Broker] = None):
        """
        初始化策略

        Args:
            broker: 可选的Broker实例，未提供时使用默认Broker（初始资金10万）
        """
        self.broker = broker or Broker()
    
    @abstractmethod
    def on_bar(self, date, get):
        """
        每个bar的处理逻辑，必须由子类实现
        
        Args:
            date: 当前时间戳
            get: 获取因子数据的函数，格式为 get(factor_name) -> pd.Series
        """
        pass