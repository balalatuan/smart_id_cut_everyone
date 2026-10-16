# Smart ID Photo Processor · Phase 1 可运行原型

这是单图可行性版本（0.2.0），不是完整 V1.0。它能在 CPU 上处理单张照片：本地脸部检测、保守头部估计、标准/自适应裁剪、JPEG 大小控制、裁剪框预览和人工矩形修正。处理引擎不依赖界面，可以替换检测器后继续发展。

**头发边界尚未验证，所有自动输出都标记 REVIEW。** 可读取但无法定位单人头像的照片也标记 REVIEW，允许人工修正；非法文件、无效人工矩形、无法达到固定尺寸/质量下限/大小上限的结果为 FAIL，不导出违规 JPEG。暂不开放自动 PASS。

## 在 Mac / Windows 安装

建议 Python 3.10–3.12；Intel Mac 优先 Python 3.11，使用新建虚拟环境，不要装入系统 Python。
下面在解压后的 smart-id-photo 目录执行。首次安装需要网络，安装完权重已随 OpenCV wheel 存在；应用不会下载模型。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
smart-id-photo-ui
```

Windows PowerShell 使用 `python -m venv .venv`，激活命令为 `.venv\Scripts\Activate.ps1`。
若 shell 不允许激活，可直接调用 `.venv\Scripts\python.exe -m pip ...` 和 `.venv\Scripts\smart-id-photo-ui.exe`。
打开 http://127.0.0.1:7860 。不启用分享链接，不对公网发布；退出终端按 Ctrl+C。
macOS/Windows 安装及 2018 MacBook Air 性能**尚未实机验证**。当前实测是 Linux CPU。
不含安装依赖的大体积虚拟环境；ZIP 可独立维护，但不是免安装二进制程序。

默认从启动目录向 output 写文件，可指定：

```bash
smart-id-photo-ui --config configs/default.yaml --output-dir /path/to/private/output
smart-id-photo examples/astronaut.png --config configs/default.yaml
smart-id-photo examples/astronaut.png --crop 142 0 307 231
```

每次输出使用随机新文件名，保留原图，JPEG 不带输入 EXIF/GPS；预览图同样包含人脸，应按敏感文件保管。
输出和浏览器上传临时文件不会自动删除。清理 output，并检查 Gradio 临时目录（系统临时目录中的 gradio 文件夹）；不要在多人共用的无保护服务器运行。

## 界面怎么用

1. 上传 JPG/JPEG/PNG，选择 standard（标准证件尺寸）或 adaptive（更宽松的头肩空间）。
2. 默认 295×413 像素、300 DPI，约 25×35 mm；可改像素尺寸。它不代表任何国家或机构的完整合规标准。
3. 选择 15 / 20 / 30 / 50 / 100 KB，上限按 **1 KB = 1024 字节**；从质量 95 向下寻找满足上限的最高整数质量，默认下限 65。质量数字不是视觉质量保证，JPEG 有损。
4. 处理后看青色脸框、橙色估计头框和绿色裁剪框。橙框不是头发分割。预览缩放至最长边 1200，坐标仍需用 EXIF 校正后的原图坐标，即使自动缩小了工作图也不变。界面会显示原图与工作图尺寸，结果的 image_info 记录缩放比例和解码尺寸。
5. 修正时勾选人工矩形，修改左/上/右/下坐标。矩形必须在图内，并匹配输出比例（允许 2% 像素取整误差）。不会生成缺失头发、换脸、修复容貌或自动美化。
6. 下载 JPEG。REVIEW 要自己检查头发、眼睛位置、肩部、清晰度和机构要求。

默认最大输入 40 百万像素和 32 MiB；工作图上限 24 百万像素，超出后自动等比例缩小，原图不改动。两者可在 YAML 分别下调。JPEG 原生降采样仅支持特定倍率，PNG 通常仍需完整解码；工作图上限不是内存占用上限。一次只解码一张图，OpenCV 单线程，界面最多排队两个请求。
不承诺阻止所有内存不足。已存在剪掉的头发无法恢复。PNG 透明像素铺白底；错误 ICC/无标记 CMYK 会提示颜色需复核。

## 云端和隐私边界

本机运行：照片在本机处理，不调用云 API，不自动上传、不自动联网下载、不启用遥测。安装依赖会联网。
云服务器或 Colab 运行：上传照片会传到该服务器，**不是本地私密离线处理**。Colab notebook 默认只演示公开样例，不自动创建分享隧道；交互界面可用 Colab 内置端口视图，需用户主动运行。Colab 运行时、端口视图、浏览器行为和数据保留政策须自行确认。
浏览器不能让程序随意访问你电脑的文件夹；CLI 读取的是 Python 运行所在机器的路径。
保存到 iCloud/OneDrive/Dropbox 等同步目录可能由同步软件独立上传。

测试检查了 Python 处理路径无远程 socket 调用；界面实测允许 loopback、阻断远程连接。它不构成操作系统级完整隔离认证，也没有浏览器全链路抓包。软件升级后应重跑离线验证。

## 复现测试与资源测量

```bash
python -m pip install -e '.[test]' --no-deps
# 如果尚未安装测试依赖：
python -m pip install 'pytest>=8,<10' 'scikit-image>=0.24,<1'
python -m pytest -q
python tools/preliminary_benchmark.py
python tools/ui_offline_smoke.py
```

最后一个命令短暂开启 127.0.0.1:7861，运行真实上传/处理/下载，然后关闭。
资源测量不含 Gradio 进程，10ms RSS 采样可能漏掉短暂峰值，不能外推 1000 张批处理或 8GB Mac。
本次升级与大图测试见 [v0.2 报告](reports/large-images-v0.2.md)；Colab 更新见 [升级说明](UPGRADE_COLAB.md)。历史基线详见 [可行性报告](reports/feasibility.md)、[实测环境](reports/environment.json)、[逐图记录](reports/preliminary-results.json)。
`requirements-tested-linux.txt` 是本次实测完整依赖锁定清单，仅供 Linux Python 3.12 复现；其他系统优先 requirements.txt。

## 分阶段状态

| 阶段 | 本次状态 |
|---|---|
| Phase 1 | 可运行单图原型、小样本基线、真实测试及资源记录；30–50 张独立参考集和分割对照未完成 |
| Phase 2 | 已提前提供单图 UI、人工矩形、压缩和离线测试；完整头发定位准确率未验证 |
| Phase 3 | 未实现 Cloud/Hybrid，不提供伪装成真实云 API 的选项 |
| Phase 4 | 未实现文件夹/ZIP 批任务、断点、暂停、AUTO 调度和 1000 张可靠性验证 |
| Phase 5 | 单图 Gradio 已实现；批次进度、联系表及批输出 ZIP 未实现 |
| Phase 6 | 已执行当前范围的测试；Mac/Windows/Colab 实机和准确率评估待验证 |

YAML 的 `future` 块是后续阶段的目标记录，**当前不生效**，不会伪称已实现调度。配置有效字段有严格验证。
`exporter.export_csv` 和 preliminary-results.csv 是单图基线运行记录导出，不是批任务系统。

接下来应先以本地保存的 30–50 张代表性图片建立独立人工参考：至少涵盖不同发型、头发颜色、背景、尺寸和照明。
用 reports/annotation-template.csv 标注实际完整头发边界、裁剪是否正确、是否剪发和修正耗时。
参考标注不能由同一个预测模型生成；冻结参数后在独立照片上评估。
验证通过后再选用 YuNet/MediaPipe/分割方案，随后实现批量调度和云插件。结构保持引擎与 UI 分离，后续无需重写压缩/导出模块。
