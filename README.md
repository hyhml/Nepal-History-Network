# Nepal History Network

一个独立、轻量的尼泊尔政治人物与组织时序图工具。项目用普通文件保存用户要求、设计规范和资料目录；Plotly 只负责生成可离线打开的交互 HTML。

在线交互图：[打开尼泊尔人物—组织网络图](https://hyhml.github.io/Nepal-History-Network/)。网站由 GitHub Pages 从 `main` 分支的 `docs/` 目录直接发布。

## 立即使用

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_chart.py
```

输出在 `output/nepal-history-network.html`。本机若有 `materials/local/datasets/raimajhi-life/`，默认使用该数据；其他机器使用仓库内的结构化示例。当前两个数据目录已同步为13个人物，人物资料依据书内第60页之前的相关内容。可用 `--data-dir` 和 `--output` 指定项目内的其他目录。

更新在线图时运行：

```bash
.venv/bin/python build_chart.py --data-dir examples/raimajhi-life --output docs/index.html --cdn
```

提交 `docs/index.html` 后，GitHub Pages 会自动发布新版本。在线图的事件悬浮说明显示书中摘录，并从 Plotly CDN 加载图表脚本以减小网页文件；本地图默认生成可离线使用的完整 HTML。党派列较多时页面可横向滚动，右侧人物聚焦栏固定在浏览器窗口内。

## 两项日常工作

记录新要求：

```bash
python3 project.py request add "希望人物聚焦时某条组织关系也高亮"
python3 project.py request list
```

要求原话进入 `docs/requests.jsonl`；落实后的规则写入 `docs/design-spec.md`，不要只改图表代码。

按目录查找资料：

```bash
python3 project.py material list
python3 project.py material list --directory materials/local/books
python3 project.py material show wty-book
python3 project.py material add /path/to/file.pdf --id another-book --title "书名" --kind books
```

目录信息保存在 `materials/catalog.json`。`material add` 会把资料复制到项目内的 `materials/local/` 并登记；该目录只在本机保存，不上传到公开仓库。资料可包含 PDF、笔记或成套 CSV。

## 边界与版本

- 程序生成的图、输入数据、资料和规范均位于本项目根目录内。`build_chart.py` 拒绝项目外的输入与输出路径。
- 扫描 PDF 存放在 `materials/local/`；仓库中的 `examples/` 保存事实表、来源定位和事件摘录，便于公开版本回滚。
- 每次设计改变都更新 `docs/design-spec.md`；稳定里程碑写入 `CHANGELOG.md` 并打 Git 标签。查看旧版可用 `git tag --list` 和 `git log --oneline`；在独立分支查看旧版可用 `git switch -c review-v0.1.0 v0.1.0`。

当前设计详见 [设计规范](docs/design-spec.md)，资料位置详见 [资料目录](materials/catalog.json)。
