# 在开头加入路径
import os, sys
import importlib

now_dir = os.getcwd()
sys.path.append(now_dir)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.common_config_manager import __version__, api_config
import soundfile as sf
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import uvicorn  
import json

# 将当前文件所在的目录添加到 sys.path
from Synthesizers.base import Base_TTS_Task, Base_TTS_Synthesizer

# 创建合成器实例
tts_synthesizer:Base_TTS_Synthesizer = None

def set_tts_synthesizer(synthesizer:Base_TTS_Synthesizer):
    global tts_synthesizer
    tts_synthesizer = synthesizer

# 存储临时文件的字典
temp_files = {}

async def character_list(request: Request):
    res = JSONResponse(tts_synthesizer.get_characters())
    return res

async def tts(request: Request):
    
    from time import time as tt
    t1 = tt()
    print(f"Request Time: {t1}")
    
    # 尝试从JSON中获取数据，如果不是JSON，则从查询参数中获取
    if request.method == "GET":
        data = request.query_params
    else:
        data = await request.json()
    
    task:Base_TTS_Task = tts_synthesizer.params_parser(data)

    if task.task_type == "text" and task.text.strip() == "":
        return HTTPException(status_code=400, detail="Text is empty")
    elif task.task_type == "ssml" and task.ssml.strip() == "":
        return HTTPException(status_code=400, detail="SSML is empty")
    md5_value = task.md5
    if task.stream == False:
        # TODO: use SQL instead of dict
        if task.save_temp and md5_value in temp_files:
            return FileResponse(path=temp_files[md5_value], media_type=f'audio/{task.format}')
        else:
            # 假设 gen 是你的音频生成器
            try:
                save_path = tts_synthesizer.generate(task, return_type="filepath")
            except Exception as e:
                return HTTPException(status_code=500, detail=str(e))
            if task.save_temp:
                temp_files[md5_value] = save_path

            t2 = tt()
            print(f"total time: {t2-t1}")
            # 返回文件响应，FileResponse 会负责将文件发送给客户端
            return FileResponse(save_path, media_type=f"audio/{task.format}", filename=os.path.basename(save_path))
    else:
        gen = tts_synthesizer.generate(task, return_type="numpy")
        return StreamingResponse(gen,  media_type='audio/wav')




if __name__ == "__main__":
    # 动态导入合成器模块, 此处可写成 from Synthesizers.xxx import TTS_Synthesizer, TTS_Task
    from importlib import import_module
    from src.api_utils import get_localhost_ipv4_address
    synthesizer_name = api_config.synthesizer
    synthesizer_module = import_module(f"Synthesizers.{synthesizer_name}")
    TTS_Synthesizer = synthesizer_module.TTS_Synthesizer
    TTS_Task = synthesizer_module.TTS_Task
    tts_synthesizer = TTS_Synthesizer(debug_mode=True)
    print(f"Backend Version: {__version__}")
    tts_host = api_config.tts_host
    tts_port = api_config.tts_port
    ipv4_address = get_localhost_ipv4_address(tts_host)
    ipv4_link = f"http://{ipv4_address}:{tts_port}"
    print(f"INFO:     Local Network URL: {ipv4_link}")
    
    app = FastAPI()

    # 设置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_api_route('/tts', tts, methods=["GET", "POST"])
    app.add_api_route('/character_list', character_list, methods=["GET"])
    uvicorn.run(app, host=tts_host, port=tts_port)

