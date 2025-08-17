import asyncio  
import uvloop  

# 替换默认事件循环为uvloop  
uvloop.install()  

async def async_task(name: str, delay: float):  
    print(f"{name} 开始执行")  
    await asyncio.sleep(delay)  # 模拟I/O耗时  
    print(f"{name} 执行完成")  

async def main():  
    # 并发执行3个任务  
    await asyncio.gather(  
        async_task("任务A", 1.0),  
        async_task("任务B", 0.5),  
        async_task("任务C", 1.5)  
    )  

if __name__ == "__main__":  
    asyncio.run(main())  # 自动使用uvloop  
