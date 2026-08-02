# AI実務レーダー

XとGitHubの一次情報から、AIエージェント、MCP、業務自動化、開発ツール、ローカルAIなどの**実務で使える情報**を自動収集し、GitHub Pagesで公開する静的サイトです。

## 仕組み

- GitHub Actionsが6時間ごとに実行
- GitHub公式APIからリリース、更新リポジトリ、反応の多いIssueを収集
- X公式APIのRecent Searchから指定条件の投稿を収集（トークン設定時のみ）
- 鮮度、具体性、実務キーワード、反応量、一次情報性を100点で採点
- 低価値情報を除外し、`data/items.json`を更新
- GitHub Pagesへ自動デプロイ

## X収集を有効にする

X APIは従量課金です。GitHubのリポジトリ設定で次を登録してください。

1. `Settings` → `Secrets and variables` → `Actions`
2. `New repository secret`
3. Name: `X_BEARER_TOKEN`
4. Secret: X Developer Consoleで発行したBearer Token

トークンがない場合もGitHub情報だけで正常に更新されます。非公式スクレイピングは行いません。

## GitHub Pagesを有効にする

1. `Settings` → `Pages`
2. `Build and deployment` の Source を `GitHub Actions` にする
3. `Actions` → `Update AI Practice Radar` → `Run workflow`

## 収集条件の変更

`config/sources.json`を編集します。

- `github_repositories`: 追跡する公式・重要リポジトリ
- `github_repository_queries`: 新しいツールを探す検索式
- `github_issue_queries`: 実務上の課題や回避策を探す検索式
- `x_queries`: XのRecent Search検索式
- `minimum_score`: 掲載する最低点
- `categories`: 自動分類ルール

## 判断上の注意

掲載点数は一次選別です。導入判断では、原文、ライセンス、セキュリティ、料金、更新履歴、再現性を必ず確認してください。
