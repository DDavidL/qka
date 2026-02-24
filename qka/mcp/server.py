from typing import Dict, Any, Optional, Callable
import asyncio
from mcp.server import FastMCP
from pathlib import Path
import pandas as pd
from datetime import datetime

class ModelServer:
    """模型服务器"""
    
    def __init__(self, port: int = 8080):
        """
        初始化模型服务器
        
        Args:
            port: 服务器端口
        """
        self.port = port
        self.models = {}
        self.running = False
    
    def register_model(self, name: str, model_func: Callable):
        """
        注册模型
        
        Args:
            name: 模型名称
            model_func: 模型函数
        """
        self.models[name] = model_func
    
    async def call_model(self, model_name: str, **kwargs) -> Any:
        """
        调用模型
        
        Args:
            model_name: 模型名称
            **kwargs: 模型参数
            
        Returns:
            模型输出结果
        """
        if model_name not in self.models:
            raise ValueError(f"模型 {model_name} 不存在")
        
        model_func = self.models[model_name]
        return await model_func(**kwargs)
    
    async def start(self):
        """启动模型服务器"""
        self.running = True
        print(f"模型服务器启动在端口 {self.port}")
    
    async def stop(self):
        """停止模型服务器"""
        self.running = False
        print("模型服务器已停止")


app = FastMCP('qka')

@app.tool()
def query_akshare_data(
        code: str = ''
) -> dict:
    """
    查询akshare数据源数据
    :param code: 查询代码，要求使用akshare库, 要求生成的函数名叫query,返回数据格式为pandas.DataFrame
    :return: 查询结果
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "无法导入akshare模块，请确认已正确安装"}

    # 限制exec命名空间，只暴露数据分析相关模块
    allowed_globals = {"__builtins__": {
        "range": range, "len": len, "list": list, "dict": dict,
        "str": str, "int": int, "float": float, "bool": bool,
        "print": print, "sorted": sorted, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter, "sum": sum,
        "min": min, "max": max, "abs": abs, "round": round,
        "isinstance": isinstance, "type": type, "tuple": tuple, "set": set,
        "True": True, "False": False, "None": None,
    }}
    allowed_globals['akshare'] = ak
    allowed_globals['ak'] = ak
    allowed_globals['pd'] = pd
    allowed_globals['pandas'] = pd
    local_namespace = {}

    try:
        exec(code, allowed_globals, local_namespace)

        # 检查是否定义了query函数
        if 'query' not in local_namespace or not callable(local_namespace['query']):
            return {"error": "代码中未定义query函数"}

        # 执行query函数（不传入参数）
        result = local_namespace['query']()

        # 检查返回结果是否为DataFrame
        if not isinstance(result, pd.DataFrame):
            return {"error": "query函数返回的结果不是DataFrame类型"}

        # 创建保存目录（使用当前工作目录下的output）
        save_dir = Path.cwd() / "output"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data_{timestamp}.csv"
        file_path = save_dir / filename

        # 保存为CSV文件
        result.to_csv(file_path, index=False, encoding='utf-8-sig')

        # 将DataFrame转换为字典返回，并包含条数信息和文件路径
        data_dict = result.to_dict(orient="records")

        return {
            "message": "数据已成功保存为CSV文件",
            "file_path": str(file_path),
            "record_count": len(data_dict),
            "data": data_dict[:10] if len(data_dict) > 10 else data_dict  # 只返回前10条预览
        }

    except Exception as e:
        return {"error": f"报错后不需要重试，执行代码时发生错误: {str(e)}"}


if __name__ == '__main__':
    app.run(transport='stdio')