# Lexivane

完全离线的 Windows 中英文记忆卡片。Python + PySide6 + SQLite。

先阅读 [项目文件与开发说明.md](项目文件与开发说明.md)：包含每个文件的用途、词库位置、开发预览和更新流程。

## 使用

双击 `dist\Lexivane.exe`，这是唯一发行版。复制它即可在受支持的 Windows 10/11 x64 电脑离线使用，无需安装 Python。

创建词库，导入每行一对中英文，检查并修正解析预览后确认。底部使用「再学 / 已会」；可以不翻面直接答题。每遍每张一次；「再学」的词会自动进入下一遍巩固，直到全部标记「已会」。新增词汇在手动开始新一轮时加入，重启可续练。词条按钮支持编辑和删除；数据与备份支持全部数据备份及合并或替换恢复。

同库按中英文词对去重，忽略大小写、全半角和多余空白。复杂混合文字需要手动修正，不会猜测答案。

## 数据

正式版：`%LOCALAPPDATA%\LexiCards\lexicards.sqlite3`。
开发版：`%LOCALAPPDATA%\LexiCards-dev\lexicards.sqlite3`，与正式版隔离。

软件从 Windows 当前用户的 LOCALAPPDATA 环境变量自动确定保存位置，首次启动自动创建数据库，无需手动配置。默认目录不是 Temp 或 exe 临时解压目录。左下角「数据与备份」可查看真实路径、打开文件夹、导出完整备份和恢复。

替换 exe 不会删除数据。建议把完整备份另外保存在熟悉的文件夹或其他磁盘；手动复制 SQLite 前退出程序，避免遗漏 WAL 日志。

## 开发

VS Code 打开本项目文件夹，已有环境直接执行：

```powershell
.\dev.bat
```

修改 `main.py`、`lexicards` 下的 Python 文件或 assets 后保存，约一秒自动重启预览。Ctrl+C 停止。未保存的界面编辑会丢失，已写入的开发词库和学习记录保留。

断点调试可按 F5（需要 VS Code 的 Python 和 Python Debugger 扩展），使用提供的开发版配置；调试模式需手动重启。

新电脑首次准备环境（建议 Python 3.13 x64）：

```powershell
python -m venv .venv
python -m pip --python .venv install -r requirements.txt
.\dev.bat
```

首次准备环境需联网下载依赖；应用运行离线。

## 测试与发布

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\build.bat
```

构建脚本检查测试、将 assets/app.png 转为多尺寸 Windows 图标，只生成 `dist\Lexivane.exe`。更新前建议备份；关闭旧版后替换新 exe 即可升级。没有在线自动更新功能。

独立目录的打包验证示例：

```powershell
$taskResult = "$PWD\smoke-results\release"
Start-Process .\dist\Lexivane.exe -ArgumentList @('--smoke-test', ('"' + $taskResult + '"')) -Wait
Get-Content "$taskResult\smoke-result.json"
```

此模式生成测试数据库、备份、截图和验证 JSON，不接触正式词库。

## 界面与人工修正

- 正常主界面、词库名称和卡片文字不可选择复制。
- 只在导入修正窗口提供原文复制：双击「原始文本（双击选词）」单元格，拖选需要的词汇，Ctrl+C 复制；也可在该只读文本框中使用右键菜单。原文不能修改。
- 双击中文或英文单元格进行修正，使用 Ctrl+V 粘贴，按 Enter 提交；编辑中的普通输入框保留标准编辑操作。
- 「再学」「已会」均可不翻面直接点击，结果照常保存。翻面仍可查看答案。
- 七套浅色外观：柔雾紫、纸页白、浅茶绿、晴空蓝、樱花粉、杏子橙、雾石灰。
- 应用图标、窗口图标、左上角品牌图片统一使用四宫辉夜。assets/app.png 保存原图，构建时重新生成 app.ico。

自行修改界面时，主要编辑 lexicards/ui.py（布局和文案）、lexicards/theme.py（配色、字体、尺寸）、lexicards/widgets.py（弹窗、原文只读选择框及表格编辑）。学习规则在 lexicards/learning.py。开发时运行 dev.bat，正式 exe 需运行 build.bat 更新。

## 自动巩固未掌握词汇

例如首次练习 30 个词，20 个已会、10 个再学：软件会立即只练这 10 个；如果还剩 4 个再学，就继续只练这 4 个，直到全部已会。每一遍内不重复，已会的词自动退出本次巩固，不需要另点「仅未掌握」。

进度条显示本次整体掌握比例，旁边显示当前第几遍及该遍进度。中途退出、切换词库或恢复完整备份，待巩固队列与进度都会保留。

随时点击「开始新一轮」可按当前设置重建练习队列，保留历史学习记录。半个月后要重新测试所有词汇时，取消「仅未掌握」并点击「开始新一轮」；以前已会的词同样会重新出现，新忘记的词会再次进入自动巩固。

「仅未掌握」只决定手动开始一轮时选择哪些词，不影响自动巩固。新增词汇不会打乱正在进行的练习，会在手动新一轮加入。旧版未完成的进度、上一遍已结束但有再学的进度，可自动接续为巩固练习。

## 上传 GitHub

保留并提交源码、assets、tests、tools、文档、requirements.txt，以及 build.bat、dev.bat、dev.py。这些脚本分别用于构建和开发预览，属于项目本身。

不提交 .venv、build、dist、缓存、生成的 .spec、个人数据库、备份及日志；.gitignore 已设置常用规则。任意命名的个人导出文件应放在项目外。已被 Git 跟踪的文件不会因添加忽略规则而自动移除。

可执行程序适合作为 GitHub Release 附件提供给普通用户，源码仓库提供给需要继续开发的人。公开文档使用项目相对路径和 Windows 环境变量，不依赖作者的用户名或本机目录。
