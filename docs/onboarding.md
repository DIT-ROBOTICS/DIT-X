# 新成員入門（第一天）

本頁是第一天的**檢查清單**，各步驟的詳細說明請參閱 [教學](tutorials/index.md)。若同一個問題卡住超過 15 分鐘，請直接向學長姐或隊友求助。

| | 工作項目 | 教學 | 時間 |
|---|---|---|---|
| ☐ | 安裝 Docker、複製（clone）shell repo、執行 `./install.sh` 與 `ditx doctor` | [01 安裝](tutorials/beginner/01-install.md) | 30 分 |
| ☐ | 執行 `ditx sync`、`ditx build`、`ditx test --integration`，確認全部通過 | [02 第一次建置與測試](tutorials/beginner/02-first-build.md) | 20 分 |
| ☐ | 輸入 `ditx`，在 TUI 中以 dry-run 模式逐一瀏覽各指令 | [03 認識 TUI](tutorials/beginner/03-tui.md) | 10 分 |
| ☐ | 使用 `ditx new` 建立一個發布 topic 的 Python node | [04 第一個套件](tutorials/beginner/04-first-package.md) | 30 分 |
| ☐ | 將 topic 登錄至 `contract.yaml` | [05 跨 domain 的 topic 與 QoS](tutorials/beginner/05-contract.md) | 20 分 |
| ☐ | 執行 `ditx up -r sim`，查看 topic、日誌與介面合約 | [06 模擬機器人](tutorials/beginner/06-sim-robot.md) | 15 分 |
| ☐ | 部署 overlay、手動復原，並觀察一次自動復原 | [07 部署 overlay 與復原](tutorials/intermediate/07-deploy.md) | 20 分 |

完成以上項目後，你已走過一次完整的開發循環：**修改程式 → 建置 → 測試 → 部署至機器人 → 復原**。

第一週內請另外閱讀：

- [09 Git 流程與 CI](tutorials/intermediate/09-git-ci.md)：在送出第一個 PR 之前閱讀
- [Architecture](architecture.md)：為何採用 shell repo 加 domain repo 的架構，以及容器如何劃分
- [Interface contract](contract.md)：目前所有跨 domain 的 topic
