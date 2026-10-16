# 样例来源

astronaut.png 使用 scikit-image 的内置 astronaut 数据：宇航员 Eileen Collins 的公开 NASA 照片。
参见 https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut 。
scikit-image 标注此 NASA 图像无已知版权限制。其余 dim/bright/small/large/blurred 是同一照片的变体，
**不算独立受试者，也不代表多种发型**。这是公开人物照片，不是私人上传照片。

synthetic.png 和 blank.png 由项目绘图代码生成；malformed.jpg 为故意无效的字节测试。
可通过 tools/preliminary_benchmark.py 重建所有样例。测试没有调用远程图片生成服务。
