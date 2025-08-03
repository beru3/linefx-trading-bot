# LINE FX Trading Bot - Python版

LINE FXの自動取引ボット（Python + Playwright版）

## 🔍 技術的特徴

### Python版の優位性
- **軽量**: Node.js版よりメモリ使用量が少ない
- **高速起動**: 仮想環境使用で起動が速い
- **豊富なライブラリ**: 将来的な機能拡張に有利
- **安定性**: asyncio による非同期処理で安定動作

### BOT検出回避機能（強化版）
- ランダム待機時間（±30%変動）
- 入力遅延ランダム化（80-120ms）
- navigator.webdriver プロパティ隠蔽
- プラグイン・言語設定の偽装
- 自然な操作シーケンス

## 📂 プロジェクト構造

```
LINEFX/
├── bot/
│   └── linefx_bot.py     # メインボット
├── config/
│   └── settings.json     # 設定ファイル
├── tests/
│   └── login_test.py     # ログインテスト
├── debug/                # スクリーンショット保存
├── logs/                 # ログファイル
├── data/                 # データ保存
├── venv/                 # Python仮想環境（自動作成）
├── requirements.txt      # Python依存関係
├── run_bot.bat          # Windows実行ファイル
├── run_bot.ps1          # PowerShell実行ファイル
└── quick_test.bat       # 簡易テスト実行
```

## 🚀 セットアップ & 実行

### 1. 自動セットアップ（推奨）
```cmd
run_bot.bat
```
このコマンドで以下が自動実行されます：
- Python仮想環境作成
- 依存関係インストール
- Playwrightブラウザインストール

### 2. 手動セットアップ
```cmd
# 仮想環境作成
python -m venv venv

# 仮想環境アクティベート
venv\Scripts\activate.bat

# 依存関係インストール
pip install -r requirements.txt

# Playwrightブラウザインストール
playwright install chromium
```

### 3. テスト実行
```cmd
# 簡易テスト
quick_test.bat

# または手動実行
python tests\login_test.py
```

## ⚙️ 設定

`config/settings.json`で以下を設定：

### ログイン情報
```json
{
  "login": {
    "url": "https://line-fx.com/signin?redirectUrl=%2F&channel=31",
    "userId": "あなたのユーザーID",
    "password": "あなたのパスワード"
  }
}
```

### BOT検出回避設定
```json
{
  "bot_settings": {
    "headless": false,
    "wait_time": {
      "min": 1000,
      "max": 3000,
      "random_variance": 0.3
    },
    "typing_delay": {
      "min": 80,
      "max": 120
    }
  }
}
```

## 🛡️ セキュリティ機能

1. **仮想環境**: システムから隔離された実行環境
2. **セレクターフォールバック**: 複数のセレクターで要素検索
3. **エラー回復**: 自動リトライとエラーログ
4. **スクリーンショット**: 各段階で証跡保存

## 📊 ログとデバッグ

### ログファイル
- 場所: `logs/bot_YYYY-MM-DD.log`
- レベル: INFO, WARNING, ERROR, DEBUG
- エンコーディング: UTF-8

### スクリーンショット
- 場所: `debug/`フォルダ
- 形式: PNG（フルページ）
- 命名: `{ステップ名}_{タイムスタンプ}.png`

## 🆚 Node.js版との比較

| 項目 | Python版 | Node.js版 |
|------|----------|-----------|
| **メモリ使用量** | **軽い** | やや重い |
| **起動速度** | **速い** | やや遅い |
| **仮想環境** | **あり** | なし |
| **ライブラリ** | **豊富** | 中程度 |
| **学習コスト** | 低い | 中程度 |
| **BOT検出回避** | 同等 | 同等 |

## 🔧 トラブルシューティング

### よくある問題

1. **Python not found**
   - Pythonをインストール: https://python.org/

2. **仮想環境エラー**
   - `venv`フォルダを削除して再実行

3. **Playwright起動失敗**
   - `playwright install chromium` を再実行

4. **ログイン失敗**
   - `debug/`フォルダのスクリーンショット確認
   - `settings.json`の認証情報確認

### ログ確認方法
```cmd
# 最新ログを表示
type logs\bot_2025-08-02.log | more
```

## 📈 実装済み取引機能

### ✅ 完成した機能
- **取引ページ解析**: HTML構造・DOM要素の自動分析
- **エントリー機能**: 買い・売り注文の自動実行
- **決済機能**: ポジション決済の自動実行
- **ポジション管理**: 現在のポジション情報取得
- **リスク管理**: 最大ポジション数・損失額制限
- **取引ログ**: 全取引の詳細ログ記録

### 🔧 取引機能の使用方法

#### 1. 取引ページ解析（安全）
```bash
# run_bot.bat → 2. Run trading page analysis
```
- 取引ページの構造を解析
- HTML構造をファイル保存  
- 取引要素の存在確認
- スクリーンショット自動保存

#### 2. 取引機能テスト
```bash  
# run_bot.bat → 3. Run trading function test
```
- 模擬取引テスト（安全）
- 実際の注文テスト（⚠️注意⚠️）
- ポジション監視

#### 3. プログラムによる取引
```python
from bot.linefx_bot import LineFXBot

# サンプル注文
orders = [
    {"type": "buy", "amount": 1000, "currency_pair": "USD/JPY"},
    {"type": "sell", "amount": 1000, "currency_pair": "EUR/JPY"}
]

bot = LineFXBot()
await bot.run_trading_session(orders)
```

### ⚙️ 取引設定

`config/settings.json`の取引設定:

```json
{
  "trading_settings": {
    "default_lot_size": 1000,
    "default_currency_pair": "USD/JPY", 
    "max_positions": 5,
    "risk_management": {
      "max_loss_per_trade": 1000,
      "stop_loss_enabled": false,
      "take_profit_enabled": false
    }
  }
}
```

## 🛡️ 安全機能

1. **段階的テスト**: 解析→模擬→実取引の3段階
2. **HTML構造保存**: デバッグ用にページ構造を保存
3. **詳細ログ**: 全操作の証跡記録
4. **スクリーンショット**: 各段階の画面キャプチャ
5. **リスク制限**: 最大ポジション・損失額の制限

## 📂 取引関連ファイル

```
LINEFX/
├── bot/
│   ├── linefx_bot.py         # メインボット（取引機能付き）
│   └── trading_utils.py      # 取引ユーティリティ
├── tests/
│   ├── login_test.py         # ログインテスト
│   └── trading_test.py       # 取引機能テスト
├── config/
│   └── settings.json         # 取引設定含む
└── data/                     # 取引履歴保存
```

## 🚨 重要な注意事項

⚠️ **実際の取引について**
- テスト環境で十分に検証してから使用
- 小額での動作確認を推奨
- 自動取引は自己責任で実行
- 市場状況により予期しない動作の可能性

## 📈 将来の拡張予定

- [ ] CSV取引データ読み込み
- [ ] Discord通知連携  
- [ ] スケジュール実行
- [ ] 高度なテクニカル分析
- [ ] ストップロス・テイクプロフィット自動設定