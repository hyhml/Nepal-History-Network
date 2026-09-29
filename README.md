# Nepal History Network

一个独立、轻量的尼泊尔政治人物与组织时序图工具。项目用普通文件保存用户要求、设计规范和资料目录；Plotly 只负责生成可离线打开的交互 HTML。

在线交互图：[打开尼泊尔人物—组织网络图](https://hyhml.github.io/Nepal-History-Network/)。网站由 GitHub Pages 从 `main` 分支的 `docs/` 目录直接发布。

## 立即使用

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_chart.py
```

输出在 `output/nepal-history-network.html`。本机若有 `materials/local/datasets/raimajhi-life/`，默认使用该数据；其他机器使用仓库内的结构化示例。当前两个数据目录已同步为26个人物、41个真实组织、18条主列和8条支线节点；原有21位共产党人物主要依据书内第60页之前的相关内容，并以导论第4页补记2012年分裂，新增5位大会党人物另使用书中相关后续章节。可用 `--data-dir` 和 `--output` 指定项目内的其他目录。

更新在线图时运行：

```bash
.venv/bin/python build_chart.py --data-dir examples/raimajhi-life --output docs/index.html --cdn
```

提交 `docs/index.html` 后，GitHub Pages 会自动发布新版本。在线图的事件悬浮说明显示书中摘录，并从 Plotly CDN 加载图表脚本以减小网页文件；本地图默认生成可离线使用的完整 HTML。党派列较多时页面可横向滚动，右侧人物聚焦栏固定在浏览器窗口内。

包含多个组织或阶段的复合列，会在列头按时间从上到下列出名称和较小的年代范围，名称本身横排并以向下箭头连接；其中的代表性组织用粗体标明。箭头只表示时间顺序和谱系归类，不必然表示直接改名或合并。向下滚动时，列头会固定在窗口顶部并随横向滚动和缩放保持对齐；单一组织列继续使用普通列名。

紫色虚线表示分裂、合并、改名、正式另立或共同组建等组织关系；紫色点线专门表示只有一部分成员并入，原组织或其余派别可能继续存在。人民统一战线按政治阵线处理，不把它误作共产党本体。

## 图表使用说明

1. **查看人物**：把鼠标停在人物节点或人物线上，可临时看清他的全部轨迹；单击可以锁定，再次单击可以取消。按住 Shift 单击，或打开“比较模式”，最多可同时选择3人。
2. **查看组织谱系**：点击图顶列名、列内空白色带，或使用右侧“选择组织列”下拉框。再次点击同一列，或选择“不选择组织列”，即可取消。
3. **组合查看**：可以同时选择人物和组织。锁定的人物最醒目，所选组织谱系中的其他人物次之，其余内容淡显。图中的100%／60%／20%只是透明度，不代表历史重要性、组织规模或史料可信度。
4. **避免误选**：人物节点和人物线用于选择人物；紫色组织关系线用于悬停查看分合详情，点击关系线不会选中它后面的整列。要选择整列，请点击列名或空白色带。
5. **恢复显示**：“全部人物”只取消人物聚焦，保留当前组织选择；按 Esc 会清除组织选择、恢复默认聚焦普拉昌达，并重置缩放和页面位置。

图中彩色纵线表示人物在相应组织中的任职或活动时段，跨列连线表示同一人物的组织轨迹；短横虚线和阶段名称用于区分同一谱系的不同时期。复合列头里的 `↓` 只表示从早到晚的排列和谱系归类，不代表直接改名、合并或无间断继承；粗体名称是该列的代表性组织。

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
