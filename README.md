# Nepal History Network

一个独立、轻量的尼泊尔政治人物与组织时序图工具。项目用普通文件保存用户要求、设计规范和资料目录；Plotly 只负责生成可离线打开的交互 HTML。

## 立即使用

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_chart.py
```

输出在 `output/adhikari-raimajhi-1954-2012.html`。本机若有 `materials/local/datasets/raimajhi-life/`，默认使用保留书中原文的本地数据；其他机器默认使用仓库内的结构化示例。可用 `--data-dir` 和 `--output` 指定项目内的其他目录。

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
- 原始扫描书和长篇原文摘录只存放在 `materials/local/`。仓库中的 `examples/` 保留事实表、来源定位和简要叙述，便于公开版本回滚。
- 每次设计改变都更新 `docs/design-spec.md`；稳定里程碑写入 `CHANGELOG.md` 并打 Git 标签。查看旧版可用 `git tag --list` 和 `git log --oneline`；在独立分支查看旧版可用 `git switch -c review-v0.1.0 v0.1.0`。

当前设计详见 [设计规范](docs/design-spec.md)，资料位置详见 [资料目录](materials/catalog.json)。
