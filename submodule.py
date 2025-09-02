import time
from queue import Queue


def blocking_main(input_param: str, message_queue: Queue):
    """阻塞的子模块主函数：往队列中推送消息"""
    # 发送开始处理消息
    message_queue.put({
        "type": "start",
        "data": {"message": f"开始处理: {input_param}"}
    })

    # 模拟阻塞处理过程（无法异步化的代码）
    total_steps = 5
    for i in range(total_steps):
        # 执行一些耗时操作
        time.sleep(1)  # 模拟阻塞等待

        # 往队列中放入进度消息
        progress = int((i + 1) / total_steps * 100)
        message_queue.put({
            "type": "progress",
            "data": {
                "message": f"处理进度 {progress}%",
                "progress": progress,
                "step": i + 1
            }
        })

    # 处理完成
    message_queue.put({
        "type": "complete",
        "data": {
            "message": f"处理完成: 结果基于 '{input_param}' 生成",
            "result": f"processed_{input_param}"
        }
    })
