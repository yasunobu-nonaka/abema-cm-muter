"""
システム音量制御機能
OS別の音量制御を実装（macOS/Windows/Linux）
"""

import platform
import subprocess
import json
from typing import Optional, Tuple
import threading
import time


class SystemController:
    """システム音量制御クラス"""
    
    def __init__(self, config: dict):
        self.config = config
        self.system = platform.system().lower()
        self.original_volume = None
        self.is_muted = False
        self.mute_volume = config['system']['mute_volume']
        self.restore_volume = config['system']['restore_volume']
        
        # 現在の音量を取得
        self._get_current_volume()
    
    def _get_current_volume(self) -> Optional[float]:
        """現在のシステム音量を取得"""
        try:
            if self.system == 'darwin':  # macOS
                return self._get_macos_volume()
            elif self.system == 'windows':
                return self._get_windows_volume()
            elif self.system == 'linux':
                return self._get_linux_volume()
            else:
                print(f"未対応のOS: {self.system}")
                return None
        except Exception as e:
            print(f"音量取得エラー: {e}")
            return None
    
    def _get_macos_volume(self) -> Optional[float]:
        """macOSの音量を取得"""
        try:
            # osascriptを使用して音量を取得
            cmd = [
                'osascript', '-e',
                'output volume of (get volume settings)'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            volume = float(result.stdout.strip())
            return volume / 100.0  # 0-1の範囲に正規化
        except Exception as e:
            print(f"macOS音量取得エラー: {e}")
            return None
    
    def _get_windows_volume(self) -> Optional[float]:
        """Windowsの音量を取得"""
        try:
            # PowerShellを使用して音量を取得
            cmd = [
                'powershell', '-Command',
                '[audio]::Volume * 100'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            volume = float(result.stdout.strip())
            return volume / 100.0  # 0-1の範囲に正規化
        except Exception as e:
            print(f"Windows音量取得エラー: {e}")
            return None
    
    def _get_linux_volume(self) -> Optional[float]:
        """Linuxの音量を取得"""
        try:
            # pactlを使用して音量を取得
            cmd = ['pactl', 'get-sink-volume', '@DEFAULT_SINK@']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # 出力例: "Volume: front-left: 32768 /  50% / -18.06 dB,   front-right: 32768 /  50% / -18.06 dB"
            output = result.stdout.strip()
            if '%' in output:
                volume_str = output.split('%')[0].split()[-1]
                volume = float(volume_str)
                return volume / 100.0  # 0-1の範囲に正規化
            return None
        except Exception as e:
            print(f"Linux音量取得エラー: {e}")
            return None
    
    def _set_macos_volume(self, volume: float) -> bool:
        """macOSの音量を設定"""
        try:
            # 0-1の範囲を0-100に変換
            volume_percent = int(volume * 100)
            
            cmd = [
                'osascript', '-e',
                f'set volume output volume {volume_percent}'
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"macOS音量設定エラー: {e}")
            return False
    
    def _set_windows_volume(self, volume: float) -> bool:
        """Windowsの音量を設定"""
        try:
            # 0-1の範囲を0-100に変換
            volume_percent = int(volume * 100)
            
            cmd = [
                'powershell', '-Command',
                f'[audio]::Volume = {volume / 100.0}'
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"Windows音量設定エラー: {e}")
            return False
    
    def _set_linux_volume(self, volume: float) -> bool:
        """Linuxの音量を設定"""
        try:
            # 0-1の範囲を0-100に変換
            volume_percent = int(volume * 100)
            
            cmd = ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{volume_percent}%']
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"Linux音量設定エラー: {e}")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """システム音量を設定"""
        try:
            # 音量を0-1の範囲に制限
            volume = max(0.0, min(1.0, volume))
            
            if self.system == 'darwin':  # macOS
                return self._set_macos_volume(volume)
            elif self.system == 'windows':
                return self._set_windows_volume(volume)
            elif self.system == 'linux':
                return self._set_linux_volume(volume)
            else:
                print(f"未対応のOS: {self.system}")
                return False
        except Exception as e:
            print(f"音量設定エラー: {e}")
            return False
    
    def mute(self) -> bool:
        """システムをミュート"""
        if self.is_muted:
            return True
        
        try:
            # 現在の音量を保存
            self.original_volume = self._get_current_volume()
            if self.original_volume is None:
                self.original_volume = self.restore_volume
            
            # ミュート
            success = self.set_volume(self.mute_volume)
            if success:
                self.is_muted = True
                print(f"システムをミュートしました (音量: {self.mute_volume})")
            return success
        except Exception as e:
            print(f"ミュートエラー: {e}")
            return False
    
    def unmute(self) -> bool:
        """システムのミュートを解除"""
        if not self.is_muted:
            return True
        
        try:
            # 元の音量に復元
            restore_volume = self.original_volume if self.original_volume is not None else self.restore_volume
            success = self.set_volume(restore_volume)
            if success:
                self.is_muted = False
                print(f"ミュートを解除しました (音量: {restore_volume})")
            return success
        except Exception as e:
            print(f"ミュート解除エラー: {e}")
            return False
    
    def toggle_mute(self) -> bool:
        """ミュート状態を切り替え"""
        if self.is_muted:
            return self.unmute()
        else:
            return self.mute()
    
    def get_volume(self) -> Optional[float]:
        """現在の音量を取得"""
        return self._get_current_volume()
    
    def get_mute_status(self) -> bool:
        """ミュート状態を取得"""
        return self.is_muted
    
    def get_system_info(self) -> dict:
        """システム情報を取得"""
        return {
            'os': self.system,
            'current_volume': self.get_volume(),
            'is_muted': self.is_muted,
            'original_volume': self.original_volume,
            'mute_volume': self.mute_volume,
            'restore_volume': self.restore_volume
        }


class VolumeController:
    """音量制御のヘルパークラス（自動復元機能付き）"""
    
    def __init__(self, system_controller: SystemController):
        self.system_controller = system_controller
        self.auto_restore_timer = None
        self.auto_restore_duration = 30  # 30秒後に自動復元
    
    def mute_with_auto_restore(self, duration: Optional[float] = None) -> bool:
        """ミュートして指定時間後に自動復元"""
        if duration is None:
            duration = self.auto_restore_duration
        
        # ミュート
        if not self.system_controller.mute():
            return False
        
        # 自動復元タイマーを設定
        if self.auto_restore_timer:
            self.auto_restore_timer.cancel()
        
        self.auto_restore_timer = threading.Timer(
            duration,
            self._auto_restore
        )
        self.auto_restore_timer.start()
        
        print(f"ミュートしました。{duration}秒後に自動復元します。")
        return True
    
    def _auto_restore(self):
        """自動復元"""
        self.system_controller.unmute()
        print("自動復元が実行されました。")
    
    def cancel_auto_restore(self):
        """自動復元をキャンセル"""
        if self.auto_restore_timer:
            self.auto_restore_timer.cancel()
            self.auto_restore_timer = None
            print("自動復元をキャンセルしました。")


def main():
    """テスト用のメイン関数"""
    # 設定を読み込み
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    controller = SystemController(config)
    volume_controller = VolumeController(controller)
    
    print("システム情報:")
    info = controller.get_system_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    try:
        print("\n音量制御テスト:")
        
        # 現在の音量を表示
        current_volume = controller.get_volume()
        print(f"現在の音量: {current_volume}")
        
        # ミュートテスト
        print("ミュート中...")
        controller.mute()
        time.sleep(2)
        
        # ミュート解除テスト
        print("ミュート解除中...")
        controller.unmute()
        time.sleep(2)
        
        # 自動復元テスト
        print("自動復元付きミュートテスト（5秒後に自動復元）...")
        volume_controller.mute_with_auto_restore(5)
        time.sleep(6)
        
        print("テスト完了")
        
    except KeyboardInterrupt:
        print("\nテストを中断しました")
    except Exception as e:
        print(f"エラー: {e}")


if __name__ == "__main__":
    main()
