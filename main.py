#!/usr/bin/env python3
"""
Abema TV CM Muter - メインアプリケーション
AbemaTVのCM音声をリアルタイムで検出し、CM再生中に自動的にPCをミュート＆画面を暗転させる
"""

import sys
import os
import json
import argparse
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from gui import CMMuterGUI
from audio_recorder import AudioRecorder
from audio_monitor import AudioMonitor
from system_controller import SystemController
from screen_controller import ScreenController


def check_dependencies():
    """依存関係をチェック"""
    try:
        import pyaudio
        import librosa
        import numpy
        import acoustid
        import tkinter
        print("✓ すべての依存関係がインストールされています")
        return True
    except ImportError as e:
        print(f"✗ 依存関係が不足しています: {e}")
        print("以下のコマンドでインストールしてください:")
        print("pip install -r requirements.txt")
        return False


def check_system_requirements():
    """システム要件をチェック"""
    import platform
    
    system = platform.system().lower()
    print(f"OS: {system}")
    
    if system == 'darwin':  # macOS
        print("✓ macOSが検出されました")
        # chromaprintの確認
        try:
            import subprocess
            result = subprocess.run(['which', 'fpcalc'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ chromaprintがインストールされています")
            else:
                print("✗ chromaprintがインストールされていません")
                print("以下のコマンドでインストールしてください:")
                print("brew install chromaprint")
                return False
        except Exception as e:
            print(f"✗ chromaprintの確認に失敗: {e}")
            return False
    
    elif system == 'windows':
        print("✓ Windowsが検出されました")
        print("注意: Windowsでは'Stereo Mix'または'What U Hear'の設定が必要な場合があります")
    
    elif system == 'linux':
        print("✓ Linuxが検出されました")
        print("注意: LinuxではPulseAudioの設定が必要な場合があります")
    
    else:
        print(f"✗ 未対応のOS: {system}")
        return False
    
    return True


def create_directories():
    """必要なディレクトリを作成"""
    directories = [
        "data",
        "data/cm_patterns"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ ディレクトリを作成しました: {directory}")


def load_config():
    """設定ファイルを読み込み"""
    config_file = "config.json"
    
    if not os.path.exists(config_file):
        print(f"✗ 設定ファイルが見つかりません: {config_file}")
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✓ 設定ファイルを読み込みました")
        return config
    except Exception as e:
        print(f"✗ 設定ファイルの読み込みに失敗: {e}")
        return None


def test_audio_devices():
    """オーディオデバイスをテスト"""
    try:
        recorder = AudioRecorder({"audio": {"sample_rate": 44100, "channels": 2, "chunk_size": 1024, "record_duration": 15, "match_threshold": 0.8, "silence_threshold": 0.01}, "system": {"mute_volume": 0.0, "restore_volume": 0.7, "screen_dim_brightness": 0.1, "overlay_opacity": 0.9}, "gui": {"window_width": 600, "window_height": 500, "theme": "default"}})
        devices = recorder.get_audio_devices()
        
        print("利用可能なオーディオデバイス:")
        for device in devices:
            print(f"  {device['index']}: {device['name']} (チャンネル: {device['channels']})")
        
        system_device = recorder.find_system_audio_device()
        print(f"システム音声デバイス: {system_device}")
        
        recorder.cleanup()
        return True
    except Exception as e:
        print(f"✗ オーディオデバイステストに失敗: {e}")
        return False


def test_system_control():
    """システム制御をテスト"""
    try:
        config = {"system": {"mute_volume": 0.0, "restore_volume": 0.7, "screen_dim_brightness": 0.1, "overlay_opacity": 0.9}}
        
        # 音量制御テスト
        system_controller = SystemController(config)
        current_volume = system_controller.get_volume()
        print(f"現在の音量: {current_volume}")
        
        # 画面制御テスト
        screen_controller = ScreenController(config)
        screen_status = screen_controller.get_screen_status()
        print(f"画面状態: {screen_status}")
        
        return True
    except Exception as e:
        print(f"✗ システム制御テストに失敗: {e}")
        return False


def run_gui():
    """GUIアプリケーションを実行"""
    try:
        print("GUIアプリケーションを起動しています...")
        app = CMMuterGUI()
        app.run()
    except Exception as e:
        print(f"✗ GUIアプリケーションの起動に失敗: {e}")
        return False
    
    return True


def run_cli():
    """コマンドラインインターフェースを実行"""
    print("コマンドラインインターフェースは未実装です")
    print("GUIアプリケーションを使用してください: python main.py --gui")
    return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Abema TV CM Muter")
    parser.add_argument("--gui", action="store_true", help="GUIアプリケーションを起動")
    parser.add_argument("--cli", action="store_true", help="コマンドラインインターフェースを起動")
    parser.add_argument("--test", action="store_true", help="システムテストを実行")
    parser.add_argument("--check", action="store_true", help="依存関係とシステム要件をチェック")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Abema TV CM Muter")
    print("=" * 50)
    
    # 依存関係とシステム要件をチェック
    if args.check or args.test:
        print("\n依存関係とシステム要件をチェック中...")
        if not check_dependencies():
            return 1
        if not check_system_requirements():
            return 1
        print("✓ すべてのチェックが完了しました")
    
    # システムテスト
    if args.test:
        print("\nシステムテストを実行中...")
        create_directories()
        
        config = load_config()
        if not config:
            return 1
        
        if not test_audio_devices():
            return 1
        
        if not test_system_control():
            return 1
        
        print("✓ すべてのテストが完了しました")
        return 0
    
    # 必要なディレクトリを作成
    create_directories()
    
    # 設定ファイルを読み込み
    config = load_config()
    if not config:
        return 1
    
    # アプリケーションを実行
    if args.cli:
        return 0 if run_cli() else 1
    else:
        # デフォルトはGUI
        return 0 if run_gui() else 1


if __name__ == "__main__":
    sys.exit(main())
