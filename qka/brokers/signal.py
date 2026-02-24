"""
QKA信号桥接服务模块

接收来自JoinQuant等外部策略平台的交易信号，转发至QMTServer执行。

用法:
    from qka.brokers.signal import signal_service
    signal_service(
        qmt_base_url="http://127.0.0.1:8000",
        qmt_token="qmt_token",
        host="0.0.0.0", port=9000,
        token="signal_token",
    )
"""

import time
import uuid
import secrets
import threading
from collections import OrderedDict
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, field_validator
import uvicorn

from qka.brokers.client import QMTClient
from qka.utils.logger import logger

# xtconstant 常量硬编码，避免依赖 xtquant
SIDE_MAP = {
    "buy": 23,   # xtconstant.STOCK_BUY
    "sell": 24,  # xtconstant.STOCK_SELL
}


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class SignalRequest(BaseModel):
    """交易信号请求"""
    symbol: str
    side: str
    quantity: int
    price: float = 0
    price_type: int = 5  # 5=最新价(市价), 11=指定价(限价)
    signal_id: Optional[str] = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        v = v.lower()
        if v not in SIDE_MAP:
            raise ValueError(f"side 必须为 'buy' 或 'sell'，收到: {v}")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity 必须大于 0")
        if v % 100 != 0:
            raise ValueError("quantity 必须为 100 的整数倍")
        return v


class SignalResponse(BaseModel):
    """交易信号响应"""
    success: bool
    signal_id: str
    order_id: Optional[str] = None
    message: str


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def normalize_stock_code(symbol: str) -> str:
    """
    规范化股票代码，确保带有交易所后缀(.SZ/.SH/.BJ)。

    支持输入格式:
        - 纯数字: "000001" → "000001.SZ"
        - 已带后缀: "000001.SZ" → 原样返回
    """
    if "." in symbol:
        # 已带后缀，直接返回
        return symbol.upper()

    code = symbol.strip()
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"股票代码必须是6位数字，收到: {symbol}")

    if code.startswith(("00", "30", "15", "16", "18", "12")):
        return f"{code}.SZ"
    elif code.startswith(("60", "68", "11")):
        return f"{code}.SH"
    elif code.startswith(("83", "43")):
        return f"{code}.BJ"

    raise ValueError(f"无法识别股票代码前缀: {code}")


# ---------------------------------------------------------------------------
# 信号去重器
# ---------------------------------------------------------------------------

class SignalDeduplicator:
    """基于 signal_id 的去重器，线程安全，带 TTL 和容量上限。"""

    def __init__(self, ttl: int = 300, max_size: int = 1000):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()
        self._ttl = ttl
        self._max_size = max_size

    def is_duplicate(self, signal_id: str) -> bool:
        """如果 signal_id 已存在且未过期则返回 True。"""
        now = time.time()
        with self._lock:
            self._evict(now)
            if signal_id in self._cache:
                return True
            self._cache[signal_id] = now
            # 容量上限
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            return False

    def _evict(self, now: float) -> None:
        while self._cache:
            oldest_key, oldest_time = next(iter(self._cache.items()))
            if now - oldest_time > self._ttl:
                self._cache.popitem(last=False)
            else:
                break


# ---------------------------------------------------------------------------
# SignalService
# ---------------------------------------------------------------------------

class SignalService:
    """
    信号桥接服务

    接收外部交易信号 (HTTP POST /signal)，通过 QMTClient 转发至 QMTServer 执行。

    Attributes:
        qmt_client: QMTClient 实例
        host: 监听地址
        port: 监听端口
        token: 访问令牌
        app: FastAPI 应用
    """

    def __init__(
        self,
        qmt_base_url: str = "http://127.0.0.1:8000",
        qmt_token: str = "",
        host: str = "0.0.0.0",
        port: int = 9000,
        token: Optional[str] = None,
    ):
        self.qmt_client = QMTClient(base_url=qmt_base_url, token=qmt_token)
        self.host = host
        self.port = port
        self.token = token or secrets.token_hex(32)
        self.dedup = SignalDeduplicator()
        self.app = FastAPI(title="QKA Signal Bridge")

        print(f"\n信号服务 Token: {self.token}\n")

        self._setup_routes()

    # -- 认证 ---------------------------------------------------------------

    async def verify_token(self, x_token: str = Header(...)):
        if x_token != self.token:
            raise HTTPException(status_code=401, detail="无效的Token")
        return x_token

    # -- 路由 ---------------------------------------------------------------

    def _setup_routes(self):
        @self.app.get("/health")
        async def health():
            return {"status": "ok"}

        @self.app.post("/signal", response_model=SignalResponse)
        async def receive_signal(
            req: SignalRequest,
            _token: str = Depends(self.verify_token),
        ):
            signal_id = req.signal_id or uuid.uuid4().hex[:12]

            # 去重
            if self.dedup.is_duplicate(signal_id):
                return SignalResponse(
                    success=False,
                    signal_id=signal_id,
                    message=f"重复信号，已忽略: {signal_id}",
                )

            # 规范化股票代码
            try:
                stock_code = normalize_stock_code(req.symbol)
            except ValueError as e:
                return SignalResponse(
                    success=False,
                    signal_id=signal_id,
                    message=str(e),
                )

            # 映射买卖方向
            order_type = SIDE_MAP[req.side]

            # 转发至 QMTServer
            try:
                result = self.qmt_client.api(
                    "order_stock",
                    stock_code=stock_code,
                    order_type=order_type,
                    order_volume=req.quantity,
                    price_type=req.price_type,
                    price=req.price,
                )
                order_id = str(result) if result is not None else None
                logger.info(
                    f"信号已转发: {req.side} {stock_code} x{req.quantity} "
                    f"signal_id={signal_id} order_id={order_id}"
                )
                return SignalResponse(
                    success=True,
                    signal_id=signal_id,
                    order_id=order_id,
                    message="信号已提交",
                )
            except Exception as e:
                logger.error(f"信号转发失败: {signal_id} {e}")
                return SignalResponse(
                    success=False,
                    signal_id=signal_id,
                    message=f"转发失败: {e}",
                )

    # -- 启动 ---------------------------------------------------------------

    def start(self):
        """启动信号桥接服务"""
        uvicorn.run(self.app, host=self.host, port=self.port)


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def signal_service(
    qmt_base_url: str = "http://127.0.0.1:8000",
    qmt_token: str = "",
    host: str = "0.0.0.0",
    port: int = 9000,
    token: Optional[str] = None,
):
    """
    快速创建并启动信号桥接服务的便捷函数

    Args:
        qmt_base_url: QMTServer 地址
        qmt_token: QMTServer 访问令牌
        host: 监听地址，默认 0.0.0.0
        port: 监听端口，默认 9000
        token: 信号服务访问令牌，不提供则自动生成
    """
    svc = SignalService(
        qmt_base_url=qmt_base_url,
        qmt_token=qmt_token,
        host=host,
        port=port,
        token=token,
    )
    svc.start()
