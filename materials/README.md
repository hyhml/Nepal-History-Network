# 资料目录

`catalog.json` 是资料索引。`path` 均以项目根目录为起点；`scope=local` 的资料在 `materials/local/`，不进入 Git。`scope=tracked` 的示例与规范可以在公开仓库中使用。

使用 `python3 project.py material list --directory <目录>` 按目录筛选，再用 `python3 project.py material show <id>` 获取文件或数据集路径。首次克隆时，本地资料会显示为“缺失”；需由持有原件的人自行导入。
