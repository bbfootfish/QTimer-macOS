# 来源与修改声明

本文件用于满足 **GNU GPL-3.0 §5a** 的要求：
分发基于他人作品修改的版本时，必须显著声明「已修改」并注明修改日期。

---

## 一、上游项目

| 项目 | 内容 |
|---|---|
| 名称 | QTimer |
| 仓库 | <https://github.com/Qwejay/QTimer> |
| 作者 | **QwejayHuang** |
| 版本 | v1.4.0 |
| Commit | `033cc23` |
| 上游发布日期 | 2026-08-26 |
| 许可证 | GNU General Public License v3.0 |

上游功能设计（多环节流转、防抢焦点、变色闪烁提醒、自定义音效、多显示器拖拽、
单实例锁、配置持久化等）全部出自原作者，本仓库未做任何功能层面的原创贡献。

---

## 二、本衍生版本

| 项目 | 内容 |
|---|---|
| 名称 | QTimer-macOS |
| 仓库 | <https://github.com/bbfootfish/QTimer-macOS> |
| 修改人 | bbfootfish |
| **修改日期** | **2026-10-10 ~ 2026-10-11** |
| 许可证 | GNU General Public License v3.0（继承上游，未变更） |

---

## 三、被修改的文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `main.py` | **已修改** | 新增 4 处 macOS 适配；文件头带修改声明注释 |
| `macos_overlay.py` | **新增** | 补丁 3：全屏穿透（置顶层修正） |
| `macos_ppt_detect.py` | **新增** | 补丁 4：PPT 放映检测 |
| `PATCHES.md` | **新增** | 补丁详解文档 |
| `README.md` | **已替换** | 改为本衍生版本的说明，上游原文存档于 `docs/README.upstream.md` |
| `NOTICE.md` | **新增** | 本文件 |
| `requirements-macos.txt` | **新增** | macOS 依赖清单 |
| `scripts/install_macos.sh` | **新增** | 安装脚本 |
| `scripts/build_standalone.sh` | **新增** | 打包脚本 |
| `default_config.json` | 未修改 | 与上游 `.qtimer_config.json` 内容一致，仅文件名不同 |
| `QTimer.icns` | 未修改 | 应用图标 |
| `LICENSE` | 未修改 | GPL-3.0 全文，原样保留 |

---

## 四、修改内容摘要

四处修改**全部为 macOS 平台适配，未改动任何业务逻辑**：

1. `ctypes.WINFUNCTYPE` 在非 Windows 平台导入期崩溃 → 改用 `CFUNCTYPE` 占位
2. 默认字体「微软雅黑」macOS 不存在 → 改用 `PingFang SC`
3. 新增窗口全屏穿透挂钩 → 修复全屏放映时悬浮窗消失
4. 新增 macOS 的 PPT 放映检测分支 → 使「PPT放映联动」真正可用

根因分析、实测数据与复现方法见 [`PATCHES.md`](PATCHES.md)。

---

## 五、许可证义务

本程序为自由软件，依据自由软件基金会发布的 **GNU 通用公共许可证第 3 版**（或更高版本）授权。
你可以依据该许可证条款重新分发和/或修改它。

本程序分发的目的是希望它有用，但**不提供任何担保**，甚至不提供适销性或特定用途适用性的默示担保。
详见 [`LICENSE`](LICENSE) 全文。

由于上游采用 GPL-3.0，本衍生版本同样以 GPL-3.0 发布，
并完整保留上游的版权声明与许可证全文。若需用于闭源商业场景，请联系上游作者获取其他授权。

---

## 六、免责

本仓库由第三方（非上游作者）维护的 macOS 适配分支。
因使用本版本产生的问题，请提交到本仓库的 Issue，而**不要**打扰上游作者。
