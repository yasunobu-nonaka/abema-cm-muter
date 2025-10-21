# Abema TV CM Muter

AbemaTV の CM 音声をリアルタイムで検出し、CM 再生中に自動的に PC をミュート＆画面を暗転させる Python アプリケーションです。

## 機能

- **音声録音・学習**: CM 音声を録音してパターンとして保存
- **リアルタイム音声監視**: システム音声を常時監視して CM を検出
- **自動ミュート**: CM 検出時にシステム音量を自動ミュート
- **画面暗転**: CM 検出時に画面を暗転（オーバーレイ・輝度調整）
- **クロスプラットフォーム**: macOS、Windows、Linux に対応
- **GUI インターフェース**: 使いやすい Tkinter ベースの GUI

## システム要件

### 共通要件

- Python 3.8 以上
- 音声出力デバイス（スピーカー・ヘッドフォン）

### macOS

- Homebrew
- chromaprint: `brew install chromaprint`
- portaudio: `brew install portaudio`

### Windows

- システム音声キャプチャ用の「Stereo Mix」または「What U Hear」設定

### Linux

- PulseAudio
- xrandr（画面輝度調整用）

## インストール

1. リポジトリをクローン

```bash
git clone https://github.com/your-username/abema-cm-muter.git
cd abema-cm-muter
```

2. 仮想環境を作成・有効化

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate  # Windows
```

3. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

4. システム要件をチェック

```bash
python main.py --check
```

## 使用方法

### GUI アプリケーション（推奨）

```bash
python main.py --gui
```

または

```bash
python main.py
```

### 基本的な使用手順

1. **CM パターンの録音**

   - 「録音開始」ボタンをクリック
   - AbemaTV で CM が流れている間に録音
   - 「録音停止」ボタンをクリックして保存

2. **音声監視の開始**

   - 「監視開始」ボタンをクリック
   - アプリケーションが CM を自動検出・対応

3. **設定の調整**
   - マッチング閾値: CM 検出の感度を調整
   - ミュート設定: CM 検出時のミュート機能の ON/OFF
   - 画面暗転設定: CM 検出時の画面暗転機能の ON/OFF

### コマンドラインオプション

```bash
# GUIアプリケーションを起動
python main.py --gui

# システムテストを実行
python main.py --test

# 依存関係とシステム要件をチェック
python main.py --check
```

## 設定

設定は`config.json`ファイルで管理されます。

```json
{
  "audio": {
    "sample_rate": 44100,
    "channels": 2,
    "chunk_size": 1024,
    "record_duration": 15,
    "match_threshold": 0.8,
    "silence_threshold": 0.01
  },
  "system": {
    "mute_volume": 0.0,
    "restore_volume": 0.7,
    "screen_dim_brightness": 0.1,
    "overlay_opacity": 0.9
  },
  "gui": {
    "window_width": 600,
    "window_height": 500,
    "theme": "default"
  }
}
```

### 設定項目の説明

- `match_threshold`: CM 検出の閾値（0.1-1.0、高いほど厳密）
- `mute_volume`: ミュート時の音量（0.0-1.0）
- `restore_volume`: 復元時の音量（0.0-1.0）
- `screen_dim_brightness`: 画面暗転時の輝度（0.0-1.0）
- `overlay_opacity`: オーバーレイの透明度（0.0-1.0）

## トラブルシューティング

### 音声が録音できない

**macOS:**

- システム環境設定 > セキュリティとプライバシー > プライバシー > マイク
- ターミナルまたは Python アプリケーションにマイクアクセス権限を付与

**Windows:**

- サウンド設定で「Stereo Mix」を有効化
- デバイスマネージャーでオーディオデバイスを確認

**Linux:**

- PulseAudio の設定を確認
- ユーザーを audio グループに追加: `sudo usermod -a -G audio $USER`

### CM が検出されない

1. マッチング閾値を下げる（0.6-0.7 程度）
2. CM パターンの録音品質を確認
3. システム音声の音量を適切に設定

### 画面が暗転しない

**macOS:**

- アクセシビリティ権限を確認
- システム環境設定 > セキュリティとプライバシー > プライバシー > アクセシビリティ

**Linux:**

- xrandr がインストールされているか確認
- ディスプレイ名を確認（通常は eDP-1）

## 開発

### プロジェクト構造

```
cm-muter/
├── src/
│   ├── audio_recorder.py    # 音声録音機能
│   ├── audio_matcher.py     # 音声マッチング機能
│   ├── audio_monitor.py     # リアルタイム監視機能
│   ├── system_controller.py # システム制御機能
│   ├── screen_controller.py # 画面制御機能
│   └── gui.py              # GUIインターフェース
├── data/
│   └── cm_patterns/        # CMパターン保存先
├── main.py                 # メインアプリケーション
├── config.json            # 設定ファイル
├── requirements.txt       # 依存パッケージ
└── README.md             # このファイル
```

### テスト

```bash
# システムテスト
python main.py --test

# 個別コンポーネントのテスト
python -m src.audio_recorder
python -m src.audio_matcher
python -m src.system_controller
python -m src.screen_controller
```

## ライセンス

MIT License

## 貢献

プルリクエストやイシューの報告を歓迎します。

## 注意事項

- このツールは教育・研究目的で作成されています
- 商用利用の際は、関連するライセンス条項を確認してください
- システム音声の録音には適切な権限設定が必要です
- CM 検出の精度は録音品質と設定に依存します
