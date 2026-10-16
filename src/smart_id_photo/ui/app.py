import os
# Gradio otherwise enables analytics by default. Set BEFORE importing it.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
import argparse
from dataclasses import replace
from pathlib import Path
import gradio as gr
from smart_id_photo.config import Config
from smart_id_photo.processor import Processor


def build_app(output_dir=None, config=None):
    base_config = config or Config()
    if output_dir is not None:
        base_config = replace(base_config, output_dir=str(output_dir))
    engine = Processor()
    theme = gr.themes.Default(font=["Arial", "sans-serif"], font_mono=["monospace"])
    with gr.Blocks(title="Smart ID Photo — Phase 1", analytics_enabled=False, theme=theme) as app:
        gr.Markdown("# Smart ID Photo · 单图原型 v0.2\n检测与处理在运行此程序的机器上完成，不另调用第三方视觉 API。自动结果为 REVIEW：完整头发边界尚未经独立验证。\n"
                    "青色：检测脸框；橙色：估计头框；绿色：裁剪框。默认 295×413 / 300 DPI，不保证任何机构合规。\n"
                    "浏览器上传会传到运行此界面的服务器。Colab 是云环境。云同步文件夹可能独立上传文件。")
        gr.Markdown(f"支持最高 **{base_config.max_pixels/1_000_000:g} 百万像素**、"
                    f"{base_config.max_input_bytes/1048576:g} MiB 的输入；"
                    f"超过 **{base_config.max_working_pixels/1_000_000:g} 百万像素**时自动等比例缩小工作图，原图不改动。"
                    "JPEG/PNG 解码仍可能暂时使用更多内存。")
        gr.Markdown("15 KB = 15,360 字节。若固定尺寸与质量下限无法同时满足大小上限，返回 FAIL 并说明原因。")
        with gr.Row():
            image = gr.File(label="单张 JPG / JPEG / PNG", file_types=[".jpg", ".jpeg", ".png"], type="filepath")
            preview = gr.Image(label="裁剪框预览（缩放显示）", interactive=False)
            output = gr.Image(label="输出 JPEG", interactive=False)
        with gr.Row():
            mode = gr.Dropdown(["standard", "adaptive"], value=base_config.mode, label="裁剪模式")
            width = gr.Number(value=base_config.width, precision=0, label="输出宽度 px")
            height = gr.Number(value=base_config.height, precision=0, label="输出高度 px")
            kb = gr.Dropdown(sorted({15,20,30,50,100,base_config.max_kb}), value=base_config.max_kb,
                             label="大小上限（1 KB = 1024 B）")
        with gr.Accordion("人工裁剪：使用 EXIF 校正后的原图像素坐标", open=False):
            manual = gr.Checkbox(label="使用人工矩形", value=False)
            with gr.Row():
                left = gr.Number(label="左 x", value=0, precision=0)
                top = gr.Number(label="上 y", value=0, precision=0)
                right = gr.Number(label="右 x", value=295, precision=0)
                bottom = gr.Number(label="下 y", value=413, precision=0)
            gr.Markdown("缩小工作图后仍填写 EXIF 校正后的原图坐标，程序自动映射。"
                        "右减左 / 下减上需匹配输出比例（±2%）；建议先自动处理，再修改结果中的 crop 坐标。")
        run = gr.Button("处理 / 应用人工裁剪", variant="primary")
        image_details = gr.Markdown("处理后将显示原图尺寸、工作图尺寸与缩小情况。")
        status = gr.JSON(label="状态、几何与限制说明")
        download = gr.File(label="下载 JPEG")

        def process(path, mode, w, h, kb, manual, l, t, r, b):
            if path is None:
                raise gr.Error("请先选择图片")
            try:
                config = replace(base_config, mode=mode, width=int(w), height=int(h), max_kb=int(kb))
            except (ValueError, TypeError) as exc:
                raise gr.Error(str(exc))
            result = engine.process(path, config, (l,t,r,b) if manual else None)
            if result.image_info:
                info = result.image_info
                original, work = info.oriented_source_size, info.working_size
                details = (f"**原图（方向已校正）：** {original[0]} × {original[1]}；"
                           f"**工作图：** {work[0]} × {work[1]}；"
                           f"**自动缩小：** {'是' if info.downsampled else '否'}。"
                           "裁剪坐标对应方向校正后的原图。")
            else:
                details = "未生成工作图。请查看下方状态与原因。"
            return result.preview, result.output, result.to_dict(), result.output, details

        run.click(process, [image,mode,width,height,kb,manual,left,top,right,bottom],
                  [preview,output,status,download,image_details], concurrency_limit=1, api_name="process")
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=7860, type=int)
    parser.add_argument("--output-dir")
    parser.add_argument("--config", help="Validated YAML configuration")
    args = parser.parse_args()
    config = Config.load(args.config) if args.config else Config()
    if args.output_dir:
        config = replace(config, output_dir=args.output_dir)
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    build_app(config=config).queue(max_size=2, default_concurrency_limit=1).launch(
        server_name=args.host, server_port=args.port, share=False, inbrowser=False,
        max_file_size=config.max_input_bytes, allowed_paths=[str(Path(config.output_dir).resolve())])


if __name__ == "__main__":
    main()
