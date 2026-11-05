# Lexivane 数据入口与公开文档验证

2026-11-05，Windows 11 x64，Python 3.13.0，PySide6-Essentials 6.10.2，PyInstaller 6.19.0。

## 当前发行文件

- dist/Lexivane.exe，39,379,336 字节。
- SHA-256：E9334E1DDA31CF2E6FE0D2F93F3EE6DFB8968B4AD44F1BAF69601BDDAC05A6E3。
- 已完成构建和启动检查，并替换 dist 中的正式成品；校验与已验证生成物一致。

## 本次修改

- 侧栏入口改为数据与备份，显示当前实例真正使用的数据库路径。
- 可打开实际数据文件夹，并进入完整备份和恢复流程。
- 保留系统默认保存位置，不搬迁数据库。开发预览仍与正式数据隔离。
- 公开文档中已移除作者用户名及绝对项目位置，统一使用项目相对路径与 Windows 环境变量。
- .gitignore 补充常见数据库、备份和日志规则。开发脚本继续保留，未上传任何 GitHub 仓库。

## 检查

- 33 项完整测试通过，包括新增的实际路径显示、只读路径、打开正确文件夹、导出可验证完整备份及恢复入口路由。
- 主界面和数据与备份窗口截图检查通过，位于 smoke-results/ui-review-data-guide-100。
- 新 exe 实际启动验证：退出代码 0，ok=true、frozen=true、icon_loaded=true、training_passes=2、mastered=2、remaining=0。
- 打包检查结果位于 smoke-results/data-release/smoke-result.json。测试使用隔离数据，不改写正式词库。
- 已用 git check-ignore 确认虚拟环境、build、dist、测试产物、常见备份、数据目录和日志被忽略，开发脚本不被忽略。
- 公开源码与 Markdown 检查未发现作者本机绝对路径或用户名；自动生成的打包描述、环境和检查产物不在公开源码范围。

本次未在另一台无 Python 的 Windows 10 主机上人工验收。默认目录不是备份，当前完整备份由用户主动导出到另外的位置，不提供自动异地备份或联网同步。
