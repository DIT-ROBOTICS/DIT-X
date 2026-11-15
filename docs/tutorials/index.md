# 教學總覽

本教學的編排方式與 [docs.ros.org](https://docs.ros.org/en/humble/Tutorials.html) 相同，每篇皆包含
**目標 → 背景 → 前置條件 → 步驟 → 摘要 → 下一步**。指令可直接複製執行，並附有預期的輸出結果。

請依序完成各篇教學，後續教學會使用前面建立的成果。

## 新手入門

| # | 教學 | 學習內容 | 時間 |
|---|---|---|---|
| 01 | [安裝](beginner/01-install.md) | 準備開發環境、取得工作區、執行 `ditx doctor` | 20 分 |
| 02 | [第一次建置與測試](beginner/02-first-build.md) | `sync` / `image` / `build` / `test` | 20 分 |
| 03 | [認識 TUI](beginner/03-tui.md) | 不需記憶指令即可操作 | 10 分 |
| 04 | [第一個套件](beginner/04-first-package.md) | `ditx new`、撰寫發布 topic 的 node、加入 bringup | 30 分 |
| 05 | [跨 domain 的 topic 與 QoS](beginner/05-contract.md) | 在 `contract.yaml` 登錄 topic、選擇 QoS | 30 分 |
| 06 | [模擬機器人](beginner/06-sim-robot.md) | `ditx up` / `topics` / `logs` / `contract live` | 15 分 |

## 中級

| # | 教學 | 學習內容 |
|---|---|---|
| 07 | [部署 overlay 與復原](intermediate/07-deploy.md) | 僅推送建置產物、驗證、自動復原 |
| 08 | [日誌與除錯](intermediate/08-debugging.md) | `build/logs`、`-v`、`ditx shell`、`ros2` 指令 |
| 09 | [Git 流程與 CI](intermediate/09-git-ci.md) | 分支、Conventional Commits、PR、CI |
| 10 | [管理機器人](intermediate/10-robots.md) | `ditx robot add/list/remove`、`robots.ini` |

## 進階

| # | 教學 | 學習內容 |
|---|---|---|
| 11 | [修改共用介面](advanced/11-interfaces.md) | `base/`、fingerprint、`--allow-skew` |
| 12 | [新增 domain](advanced/12-new-domain.md) | repo、`ditx.repos`、compose service、bringup 慣例 |
| 13 | [撰寫 plugin](advanced/13-plugins.md) | `tools/ext/ditx-<name>` |
| 14 | [arm64 與實體機器人](advanced/14-real-robot.md) | `infra/robot/install.sh`、SSH、`--arch arm64` |
| 15 | [C++ 開發環境](advanced/15-cpp.md) | clangd、`ditx index`、Dev Container |
