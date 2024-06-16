from datetime import datetime
import gradio as gr
import json, os
import requests
import numpy as np
from string import Template
import wave, io

# 在开头加入路径
import os, sys
now_dir = os.getcwd()
sys.path.insert(0, now_dir)

import logging
logging.getLogger("markdown_it").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("charset_normalizer").setLevel(logging.ERROR)
logging.getLogger("torchaudio._extension").setLevel(logging.ERROR)

from Synthesizers.base import Base_TTS_Synthesizer, Base_TTS_Task, get_wave_header_chunk
from src.common_config_manager import app_config, __version__

frontend_version = __version__

def load_character_emotions(character_name, characters_and_emotions):
    emotion_options = ["default"]
    emotion_options = characters_and_emotions.get(character_name, ["default"])

    return gr.Dropdown(emotion_options, value="default")

synthesizer_name = app_config.synthesizer

from importlib import import_module
import tools.i18n.i18n as i18n_module


# 设置国际化支持
i18n = i18n_module.I18nAuto(language=app_config.locale, locale_path=f"Synthesizers/{synthesizer_name}/configs/i18n/locale")

# 动态导入合成器模块, 此处可写成 from Synthesizers.xxx import TTS_Synthesizer, TTS_Task
synthesizer_module = import_module(f"Synthesizers.{synthesizer_name}")
TTS_Synthesizer = synthesizer_module.TTS_Synthesizer
TTS_Task = synthesizer_module.TTS_Task


# 创建合成器实例
tts_synthesizer:Base_TTS_Synthesizer = TTS_Synthesizer(debug_mode=True)

import soundfile as sf

all_gradio_components = {}

from time import time as ttime

def get_audio(*data, streaming=False):

    
    data = dict(zip([key for key in all_gradio_components.keys()], data))
    data["stream"] = streaming
    
    if data.get("text") in ["", None]:
        gr.Warning(i18n("文本不能为空"))
        return None, None
    try:
        task: Base_TTS_Task= tts_synthesizer.params_parser(data)
        t2 = ttime()
        
        if not streaming:
            if synthesizer_name == "remote":
                save_path = tts_synthesizer.generate(task, return_type="filepath")
                yield save_path
            else:
                gen = tts_synthesizer.generate(task, return_type="numpy")
                yield next(gen)
        else:
            gen = tts_synthesizer.generate(task, return_type="numpy")
            sample_rate = 32000 if task.sample_rate in [None, 0] else task.sample_rate
            yield get_wave_header_chunk(sample_rate=sample_rate)
            for chunk in gen:
                yield chunk
        
    except Exception as e:
        gr.Warning(f"Error: {e}")


from functools import partial
get_streaming_audio = partial(get_audio, streaming=True)

def stopAudioPlay():
    return


global characters_and_emotions_dict
characters_and_emotions_dict = {}

def get_characters_and_emotions():
    global characters_and_emotions_dict
    # 直接检查字典是否为空，如果不是，直接返回，避免重复获取
    if characters_and_emotions_dict == {}:
        characters_and_emotions_dict = tts_synthesizer.get_characters()
        print(characters_and_emotions_dict)
   
    return characters_and_emotions_dict

def change_character_list(
    character="", emotion="default"
):
    characters_and_emotions = {}

    try:
        characters_and_emotions = get_characters_and_emotions()
        character_names = [i for i in characters_and_emotions]
        if len(character_names) != 0:
            if character in character_names:
                character_name_value = character
            else:
                character_name_value = character_names[0]
        else:
            character_name_value = ""
        emotions = characters_and_emotions.get(character_name_value, ["default"])
        emotion_value = emotion

    except:
        character_names = []
        character_name_value = ""
        emotions = ["default"]
        emotion_value = "default"
        characters_and_emotions = {}

    return (
        gr.Dropdown(character_names, value=character_name_value, label=i18n("选择角色")),
        gr.Dropdown(emotions, value=emotion_value, label=i18n("情感列表"), interactive=True),
        characters_and_emotions,
    )


def cut_sentence_multilang(text, max_length=30):
    if max_length == -1:
        return text, ""
    # 初始化计数器
    word_count = 0
    in_word = False
    
    
    for index, char in enumerate(text):
        if char.isspace():  # 如果当前字符是空格
            in_word = False
        elif char.isascii() and not in_word:  # 如果是ASCII字符（英文）并且不在单词内
            word_count += 1  # 新的英文单词
            in_word = True
        elif not char.isascii():  # 如果字符非英文
            word_count += 1  # 每个非英文字符单独计为一个字
        if word_count > max_length:
            return text[:index], text[index:]
    
    return text, ""


default_text = i18n("我是一个粉刷匠，粉刷本领强。我要把那新房子，刷得更漂亮。刷了房顶又刷墙，刷子像飞一样。哎呀我的小鼻子，变呀变了样。")


information = ""

try:
    with open("Information.md", "r", encoding="utf-8") as f:
        information = f.read()
except:
    pass
try:    
    max_text_length = app_config.max_text_length
except:
    max_text_length = -1

from webuis.builders.gradio_builder import GradioTabBuilder

ref_settings = tts_synthesizer.ui_config.get("ref_settings", [])
basic_settings = tts_synthesizer.ui_config.get("basic_settings", [])
advanced_settings = tts_synthesizer.ui_config.get("advanced_settings", [])
url_setting = tts_synthesizer.ui_config.get("url_settings", [])

tts_task_example : Base_TTS_Task = TTS_Task()
params_config = tts_task_example.params_config

has_character_param = True if "character" in params_config else False

with gr.Blocks() as app:
    gr.Markdown(information)
    with gr.Row():
        max_text_length_tip = "" if max_text_length == -1 else f"( "+i18n("最大允许长度")+ f" : {max_text_length} ) "
        text = gr.Textbox(
            value=default_text, label=i18n("输入文本")+max_text_length_tip, interactive=True, lines=8
        )
        text.blur(lambda x: gr.update(value=cut_sentence_multilang(x,max_length=max_text_length)[0]), [text], [text])
        all_gradio_components["text"] = text
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab(label=i18n("角色选项"), visible=has_character_param):
                    with gr.Group():
                        (
                            character,
                            emotion,
                            characters_and_emotions_,
                        ) = change_character_list()
                        characters_and_emotions = gr.State(characters_and_emotions_)
                        scan_character_list = gr.Button(
                            i18n("扫描人物列表"), variant="secondary"
                        )
                    all_gradio_components["character"] = character
                    all_gradio_components["emotion"] = emotion
                    character.change(
                        load_character_emotions,
                        inputs=[character, characters_and_emotions],
                        outputs=[emotion],
                    )

                    scan_character_list.click(
                        change_character_list,
                        inputs=[character, emotion],
                        outputs=[
                            character,
                            emotion,
                            characters_and_emotions,
                        ],
                    )
                if len(ref_settings) > 0:
                    with gr.Tab(label=i18n("参考设置")):
                        ref_settings_tab = GradioTabBuilder(
                            ref_settings, params_config
                        )
                        ref_settings_components = ref_settings_tab.build()
                        all_gradio_components.update(ref_settings_components)
        with gr.Column(scale=2):
            with gr.Tabs():
                if len(basic_settings) > 0:
                    with gr.Tab(label=i18n("基础选项")):
                        basic_settings_tab = GradioTabBuilder(
                            basic_settings, params_config
                        )
                        basic_settings_components = basic_settings_tab.build()
                        all_gradio_components.update(basic_settings_components)
        with gr.Column(scale=2):
            with gr.Tabs():
                if len(advanced_settings) > 0:
                    with gr.Tab(label=i18n("高级选项")):
                        advanced_settings_tab = GradioTabBuilder(
                            advanced_settings, params_config
                        )
                        advanced_settings_components = advanced_settings_tab.build()
                        all_gradio_components.update(advanced_settings_components)
                if len(url_setting) > 0:
                    with gr.Tab(label=i18n("URL设置")):
                        url_setting_tab = GradioTabBuilder(url_setting, params_config)
                        url_setting_components = url_setting_tab.build()
                        all_gradio_components.update(url_setting_components)
    with gr.Tabs():
        with gr.Tab(label=i18n("请求完整音频")):
            with gr.Row():
                get_full_audio_button = gr.Button(i18n("生成音频"), variant="primary")
                full_audio = gr.Audio(
                    None, label=i18n("音频输出"), type="filepath", streaming=False
                )
                get_full_audio_button.click(lambda: gr.update(interactive=False), None, [get_full_audio_button]).then(
                    get_audio,
                    inputs=[value for key, value in all_gradio_components.items()],
                    outputs=[full_audio],
                ).then(lambda: gr.update(interactive=True), None, [get_full_audio_button])
        with gr.Tab(label=i18n("流式音频")):
            with gr.Row():
                get_streaming_audio_button = gr.Button(i18n("生成流式音频"), variant="primary")
                streaming_audio = gr.Audio(
                    None, label=i18n("音频输出"), type="filepath", streaming=True, autoplay=True
                )
                get_streaming_audio_button.click(lambda: gr.update(interactive=False), None, [get_streaming_audio_button]).then(
                    get_streaming_audio,
                    inputs=[value for key, value in all_gradio_components.items()],
                    outputs=[streaming_audio],
                ).then(lambda: gr.update(interactive=True), None, [get_streaming_audio_button])

    gr.HTML("<hr style='border-top: 1px solid #ccc; margin: 20px 0;' />")
    gr.HTML(
        f"""<p>{i18n("这是GSVI。")}{i18n("，当前版本：")}<a href="https://www.yuque.com/xter/zibxlp/awo29n8m6e6soru9">{frontend_version}</a>  {i18n("项目开源地址：")} <a href="https://github.com/X-T-E-R/GPT-SoVITS-Inference">Github</a></p>
            <p>{i18n("若有疑问或需要进一步了解，可参考文档：")}<a href="{i18n("https://www.yuque.com/xter/zibxlp")}">{i18n("点击查看详细文档")}</a>。</p>"""
    )
    # 以下是事件绑定
    # app.load(
    #     change_character_list,
    #     inputs=[character,  emotion],
    #     outputs=[
    #         character,
    #         emotion,
    #         characters_and_emotions,
    #     ]
    # )            


if app_config.also_enable_api == True:
    import uvicorn
    from pure_api import tts, character_list, set_tts_synthesizer
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from src.api_utils import get_gradio_frp, get_localhost_ipv4_address
    
    set_tts_synthesizer(tts_synthesizer)
    fastapi_app:FastAPI = app.app
    fastapi_app.add_api_route("/tts", tts, methods=["POST", "GET"])
    fastapi_app.add_api_route("/character_list", character_list, methods=["GET"])
    
    fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    local_link = f"http://127.0.0.1:{app_config.server_port}"
    link = local_link
    if app_config.is_share:
        share_url = get_gradio_frp(app_config.server_name, app_config.server_port, app.share_token)
        print("This share link expires in 72 hours.")
        print(f"Share URL: {share_url}")
        link = share_url
    if app_config.inbrowser:
        import webbrowser
        webbrowser.open(link)

    ipv4_address = get_localhost_ipv4_address(app_config.server_name)
    ipv4_link = f"http://{ipv4_address}:{app_config.server_port}"
    print(f"INFO:     Local Network URL: {ipv4_link}")
    
    fastapi_app = gr.mount_gradio_app(fastapi_app, app, path="/")
    uvicorn.run(fastapi_app, host=app_config.server_name, port=app_config.server_port)
else:
    app.queue().launch(share=app_config.is_share, inbrowser=app_config.inbrowser, server_name=app_config.server_name, server_port=app_config.server_port)

