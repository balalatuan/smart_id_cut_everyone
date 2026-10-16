# Colab 从 v0.1 升级到 v0.2

本次只增加 4000 万像素输入、工作图自动缩小、原图坐标映射和 15 KB 选项，未实现批任务。没有新增依赖，默认质量下限仍为 65，默认文件大小仍为 50 KB。

## 已安装过旧版的 Colab 会话

先把 Smart_ID_Photo_v0.2_LargeImages_15KB.zip 下载到电脑。下载旧的处理结果后，选择 Colab「运行时 / 代码执行程序 → 重启会话」，释放旧版本 Python 模块及 Gradio 服务。不要删除运行时；普通重启通常保留已安装依赖和 /content 文件，但仍应先下载重要结果。

点击「+ 代码」，运行下列单元，选择**新版项目 ZIP**。它将代码解压到 /content/smart-id-v02，不改动 Google Drive 中的旧项目或原照片。不要选择测试照片 ZIP。

```python
import io
import os
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from google.colab import files

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
uploaded = files.upload()
if len(uploaded) != 1:
    raise ValueError("请选择一个新版项目 ZIP")

base = Path("/content/smart-id-v02")
base.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(next(iter(uploaded.values())))) as archive:
    entries = archive.infolist()
    if len(entries) > 1000 or sum(i.file_size for i in entries) > 200_000_000:
        raise ValueError("ZIP 太大")
    for item in entries:
        p = PurePosixPath(item.filename)
        if (p.is_absolute() or ".." in p.parts or "\\" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)
                or not p.parts or p.parts[0] != "smart-id-photo"):
            raise ValueError("不是安全的项目 ZIP")
    archive.extractall(base)

project = base / "smart-id-photo"
sys.path.insert(0, str(project / "src"))
from smart_id_photo import __version__
from smart_id_photo.config import Config
assert __version__ == "0.2.0", "仍加载旧代码，请重启会话后重新运行这一格"
print("项目版本：", __version__)
print("输入像素上限：", Config().max_pixels)
print("工作图像素上限：", Config().max_working_pixels)
```

应显示 0.2.0 / 40000000 / 24000000。此方式直接从新版源码导入，不依赖旧版 editable 安装路径。如果提示缺少模块，再安装项目 requirements.txt 并按 Colab 提示重启。

另开一个代码格启动界面：

```python
from smart_id_photo.ui.app import build_app
from google.colab import output

output_dir = "/content/smart-id-ui-output-v02"
Path(output_dir).mkdir(parents=True, exist_ok=True)
app = build_app(output_dir)
app.queue(max_size=2, default_concurrency_limit=1).launch(
    server_name="127.0.0.1", server_port=7860, share=False,
    inline=False, prevent_thread_lock=True,
    max_file_size=32 * 1024 * 1024, allowed_paths=[output_dir]
)
output.serve_kernel_port_as_iframe(7860, height=1000)
```

先重试 4480×6536 原图，查看原图/工作图尺寸提示；再选择 15 KB。输出仍为 REVIEW，并不代表头发或全身小脸检测已验证准确。

## 若界面下载再次出现 502

这不是已解决的功能：Colab 的嵌入界面下载链接可能不可用。打开 Colab 左侧文件栏，定位 `/content/smart-id-ui-output-v02`，找到 JSON `output` 对应的 JPG，右键下载；或使用：

```python
from google.colab import files
files.download("这里填写结果 JSON 中 output 的完整路径")
```

## 本机更新

解压新版到一个新文件夹，避免覆盖旧项目中的 input/output。激活自己的虚拟环境，执行 `python -m pip install -e . --no-deps`，重新启动界面。可使用 `smart-id-photo-ui --config configs/default.yaml` 加载自定义配置。

Colab 是 Google 云端。上传私照会传到云端；/content 的临时文件应及时下载。新版未在你的 Colab 会话内执行，不能自动替换你正在运行的程序。
