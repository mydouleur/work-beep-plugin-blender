"""桥命令模块汇总：import 即注册（各模块用 @command 装饰器的副作用填充注册表）。

新增命令文件后在这里加一行 import。
"""

from . import view  # noqa: F401
