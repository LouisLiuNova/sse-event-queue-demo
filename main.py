from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from enum import  StrEnum
from typing import AsyncGenerator, Dict
import threading
from queue import Queue  # 线程安全的队列
from submodule import blocking_main  # 导入阻塞的子模块主函数
import uvicorn
app = FastAPI(title="FastAPI SSE with Blocking Submodule")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 定义事件状态枚举
class Status(StrEnum):
    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    END = "end"
    ERROR = "error"


def format_sse(data: Dict, event: str = None) -> str:
    """格式化SSE消息"""
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data,ensure_ascii=False)}")
    lines.append("")  # 空行结束
    return "\n".join(lines)


def run_blocking_module(input_param: str, message_queue: Queue):
    """在独立线程中运行阻塞子模块"""
    try:
        # 调用阻塞子模块的主函数，将队列作为参数传入
        # 子模块在处理过程中会往队列中放入消息
        blocking_main(input_param, message_queue)

        # 所有处理完成后，放入结束消息
        message_queue.put({
            "type": Status.END.value,
            "data": {"message": "子模块处理全部完成"}
        })
    except Exception as e:
        # 捕获子模块中的异常并放入队列
        message_queue.put({
            "type": Status.ERROR.value,
            "data": {"message": f"处理出错: {str(e)}"}
        })


async def event_generator(input_param: str) -> AsyncGenerator[str, None]:
    """SSE事件生成器：异步读取队列并发送消息"""
    # 创建线程安全的队列（用于阻塞线程和异步事件循环之间通信）
    message_queue = Queue()

    # 启动独立线程运行阻塞子模块
    thread = threading.Thread(
        target=run_blocking_module,
        args=(input_param, message_queue),
        daemon=True  # 确保主线程退出时子线程也会退出
    )
    thread.start()

    try:
        # 发送初始连接事件
        yield format_sse(
            data={"message": "已连接，开始处理请求"},
            event=Status.START.value()
        )

        # 持续从队列读取消息
        while True:
            # 检查线程是否还在运行且队列是否为空
            if not thread.is_alive() and message_queue.empty():
                break

            # 非阻塞地检查队列（超时0.1秒）
            try:
                # 在异步环境中使用同步队列的get方法，设置超时避免阻塞事件循环
                message = message_queue.get(block=False, timeout=0.1)
                yield format_sse(
                    data=message["data"],
                    event=message["type"]
                )
                message_queue.task_done()
            except Exception:
                # 队列为空时短暂等待，让出CPU
                await asyncio.sleep(0.1)
                continue

    except asyncio.CancelledError:
        # 客户端断开连接时清理
        print(f"Client disconnected")
    finally:
        print(f"Stream closed")


@app.get("/stream/{input_param}")
async def stream_data(input_param: str) -> StreamingResponse:
    """SSE流接口：处理阻塞子模块的请求"""
    return StreamingResponse(
        event_generator(input_param),
        media_type="text/event-stream"
    )


if __name__ == "__main__":


    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
