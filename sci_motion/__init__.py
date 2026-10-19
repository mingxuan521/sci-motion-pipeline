"""sci-motion-pipeline · 中文科学可视化视频流水线。

把一段中文科学解说词，自动变成一条带配音、有运动感的成品视频。
纯 CPU 也能跑通全部流程；有显卡时可接入 I2V 模型升级为真实运动画面。
"""

__version__ = "0.1.0"

from .config import Config, load_config  # noqa: F401

__all__ = ["Config", "load_config", "__version__"]
