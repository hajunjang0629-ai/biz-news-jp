# BizNews JP

世界中のビジネスニュースから、**本当に読む価値のある記事だけ**を自動選別し、**すべて日本語に翻訳**して表示するウェブサイトです。

## 機能

- 複数の国際ビジネスRSS（BBC、CNBC、Bloomberg、Reuters、NPR）から記事を取得
- M&A、IPO、AI、規制、大型投資などのキーワードで「注目度」をスコアリング
- 低スコアの記事を除外し、厳選ニュースのみ表示
- タイトル・概要・タグを自動的に日本語へ翻訳
- 記事ごとの共有URL（`/article/{id}`）
- X / LINE / リンクコピーで共有
- SNSプレビュー用 OG タグ対応

## ローカル実行

```bash
cd biz-news-jp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

ブラウザで [http://127.0.0.1:8000](http://127.0.0.1:8000) を開いてください。

## インターネット公開（共有）

### Render（おすすめ・無料枠あり）

1. [Render](https://render.com/) に GitHub リポジトリを連携
2. **New → Blueprint** または **Web Service** を作成
3. リポジトリ root の `render.yaml` を使用
4. 環境変数 `BASE_URL` に公開URLを設定  
   例: `https://biz-news-jp.onrender.com`
5. デプロイ完了後、そのURLを共有

### Docker

```bash
docker build -t biz-news-jp .
docker run -p 8000:8000 -e BASE_URL=http://localhost:8000 biz-news-jp
```

## 共有URL

| 種類 | URL |
|------|-----|
| サイトトップ | `https://your-domain/` |
| 記事 | `https://your-domain/article/{記事ID}` |

記事を開くとURLが自動更新され、モーダル内から X / LINE / リンクコピーで共有可能です。

## API

- `GET /` — 日本語ニュース一覧ページ
- `GET /article/{id}` — 記事共有ページ（OGタグ付き）
- `GET /api/news` — JSON形式の厳選ニュース
- `GET /api/articles/{id}/body` — 記事本文（日本語翻訳）
- `POST /api/refresh` — 最新記事を再取得・再翻訳

## 注意

- 翻訳は Google Translate（非公式API）を利用しています。ネットワーク接続が必要です。
- RSSフィードの可用性は各メディア側の設定に依存します。
- 本番公開時は `BASE_URL` を設定すると、SNSシェア時のプレビューURLが正しくなります。
