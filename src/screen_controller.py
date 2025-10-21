"""
画面暗転機能
CM検出時に画面を暗転させる（オーバーレイ・輝度調整）
"""

import tkinter as tk
from tkinter import ttk
import platform
import subprocess
import threading
import time
from typing import Optional, Callable


class ScreenController:
    """画面暗転制御クラス"""
    
    def __init__(self, config: dict):
        self.config = config
        self.system = platform.system().lower()
        self.overlay_window = None
        self.is_darkened = False
        self.overlay_opacity = config['system']['overlay_opacity']
        self.screen_dim_brightness = config['system']['screen_dim_brightness']
        
        # 元の画面設定を保存
        self.original_brightness = None
    
    def create_overlay_window(self) -> tk.Toplevel:
        """全画面オーバーレイウィンドウを作成"""
        # メインウィンドウを取得（存在しない場合は作成）
        root = tk._default_root
        if root is None:
            root = tk.Tk()
            root.withdraw()  # メインウィンドウを非表示
        
        # オーバーレイウィンドウを作成
        overlay = tk.Toplevel(root)
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-topmost', True)
        overlay.attributes('-alpha', self.overlay_opacity)
        overlay.configure(bg='black')
        
        # ウィンドウを最前面に表示
        overlay.lift()
        overlay.focus_force()
        
        # キーボードイベントを無効化
        overlay.bind('<Key>', lambda e: None)
        overlay.bind('<Button>', lambda e: None)
        
        return overlay
    
    def show_overlay(self) -> bool:
        """画面オーバーレイを表示"""
        try:
            if self.overlay_window is not None:
                return True  # 既に表示中
            
            self.overlay_window = self.create_overlay_window()
            self.is_darkened = True
            print("画面オーバーレイを表示しました")
            return True
            
        except Exception as e:
            print(f"オーバーレイ表示エラー: {e}")
            return False
    
    def hide_overlay(self) -> bool:
        """画面オーバーレイを非表示"""
        try:
            if self.overlay_window is not None:
                self.overlay_window.destroy()
                self.overlay_window = None
                self.is_darkened = False
                print("画面オーバーレイを非表示にしました")
            return True
            
        except Exception as e:
            print(f"オーバーレイ非表示エラー: {e}")
            return False
    
    def _get_macos_brightness(self) -> Optional[float]:
        """macOSの画面輝度を取得"""
        try:
            cmd = [
                'osascript', '-e',
                'tell application "System Events" to tell process "SystemUIServer" to get value of slider 1 of group 1 of group 1 of group 2 of bar 1 of group 1 of menu bar 1'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            brightness = float(result.stdout.strip())
            return brightness / 100.0  # 0-1の範囲に正規化
        except Exception as e:
            print(f"macOS輝度取得エラー: {e}")
            return None
    
    def _set_macos_brightness(self, brightness: float) -> bool:
        """macOSの画面輝度を設定"""
        try:
            # 0-1の範囲を0-100に変換
            brightness_percent = int(brightness * 100)
            
            cmd = [
                'osascript', '-e',
                f'tell application "System Events" to tell process "SystemUIServer" to set value of slider 1 of group 1 of group 1 of group 2 of bar 1 of group 1 of menu bar 1 to {brightness_percent}'
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"macOS輝度設定エラー: {e}")
            return False
    
    def _get_windows_brightness(self) -> Optional[float]:
        """Windowsの画面輝度を取得"""
        try:
            cmd = [
                'powershell', '-Command',
                '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            brightness = float(result.stdout.strip())
            return brightness / 100.0  # 0-1の範囲に正規化
        except Exception as e:
            print(f"Windows輝度取得エラー: {e}")
            return None
    
    def _set_windows_brightness(self, brightness: float) -> bool:
        """Windowsの画面輝度を設定"""
        try:
            # 0-1の範囲を0-100に変換
            brightness_percent = int(brightness * 100)
            
            cmd = [
                'powershell', '-Command',
                f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {brightness_percent})'
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"Windows輝度設定エラー: {e}")
            return False
    
    def _get_linux_brightness(self) -> Optional[float]:
        """Linuxの画面輝度を取得"""
        try:
            # xrandrを使用して輝度を取得
            cmd = ['xrandr', '--verbose']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # 出力から輝度を抽出
            for line in result.stdout.split('\n'):
                if 'Brightness:' in line:
                    brightness = float(line.split('Brightness:')[1].strip())
                    return brightness
            return None
        except Exception as e:
            print(f"Linux輝度取得エラー: {e}")
            return None
    
    def _set_linux_brightness(self, brightness: float) -> bool:
        """Linuxの画面輝度を設定"""
        try:
            # xrandrを使用して輝度を設定
            cmd = ['xrandr', '--output', 'eDP-1', '--brightness', str(brightness)]
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"Linux輝度設定エラー: {e}")
            return False
    
    def dim_screen(self) -> bool:
        """画面を暗くする"""
        try:
            if self.system == 'darwin':  # macOS
                # 元の輝度を保存
                self.original_brightness = self._get_macos_brightness()
                return self._set_macos_brightness(self.screen_dim_brightness)
            elif self.system == 'windows':
                self.original_brightness = self._get_windows_brightness()
                return self._set_windows_brightness(self.screen_dim_brightness)
            elif self.system == 'linux':
                self.original_brightness = self._get_linux_brightness()
                return self._set_linux_brightness(self.screen_dim_brightness)
            else:
                print(f"未対応のOS: {self.system}")
                return False
        except Exception as e:
            print(f"画面暗転エラー: {e}")
            return False
    
    def restore_screen(self) -> bool:
        """画面を元に戻す"""
        try:
            if self.original_brightness is None:
                return True  # 元の設定がない場合は何もしない
            
            if self.system == 'darwin':  # macOS
                return self._set_macos_brightness(self.original_brightness)
            elif self.system == 'windows':
                return self._set_windows_brightness(self.original_brightness)
            elif self.system == 'linux':
                return self._set_linux_brightness(self.original_brightness)
            else:
                print(f"未対応のOS: {self.system}")
                return False
        except Exception as e:
            print(f"画面復元エラー: {e}")
            return False
    
    def darken_screen(self, method: str = 'overlay') -> bool:
        """画面を暗転させる"""
        try:
            if method == 'overlay':
                return self.show_overlay()
            elif method == 'brightness':
                return self.dim_screen()
            elif method == 'both':
                overlay_success = self.show_overlay()
                brightness_success = self.dim_screen()
                return overlay_success or brightness_success
            else:
                print(f"未対応の暗転方法: {method}")
                return False
        except Exception as e:
            print(f"画面暗転エラー: {e}")
            return False
    
    def brighten_screen(self, method: str = 'overlay') -> bool:
        """画面を明るくする"""
        try:
            if method == 'overlay':
                return self.hide_overlay()
            elif method == 'brightness':
                return self.restore_screen()
            elif method == 'both':
                overlay_success = self.hide_overlay()
                brightness_success = self.restore_screen()
                return overlay_success and brightness_success
            else:
                print(f"未対応の明転方法: {method}")
                return False
        except Exception as e:
            print(f"画面明転エラー: {e}")
            return False
    
    def get_screen_status(self) -> dict:
        """画面状態を取得"""
        return {
            'is_darkened': self.is_darkened,
            'overlay_active': self.overlay_window is not None,
            'original_brightness': self.original_brightness,
            'current_brightness': self._get_macos_brightness() if self.system == 'darwin' else None,
            'system': self.system
        }


class ScreenControllerWithTimer:
    """タイマー機能付き画面制御クラス"""
    
    def __init__(self, screen_controller: ScreenController):
        self.screen_controller = screen_controller
        self.auto_restore_timer = None
        self.auto_restore_duration = 30  # 30秒後に自動復元
    
    def darken_with_auto_restore(self, method: str = 'overlay', duration: Optional[float] = None) -> bool:
        """画面を暗転して指定時間後に自動復元"""
        if duration is None:
            duration = self.auto_restore_duration
        
        # 画面を暗転
        if not self.screen_controller.darken_screen(method):
            return False
        
        # 自動復元タイマーを設定
        if self.auto_restore_timer:
            self.auto_restore_timer.cancel()
        
        self.auto_restore_timer = threading.Timer(
            duration,
            self._auto_restore,
            args=(method,)
        )
        self.auto_restore_timer.start()
        
        print(f"画面を暗転しました。{duration}秒後に自動復元します。")
        return True
    
    def _auto_restore(self, method: str):
        """自動復元"""
        self.screen_controller.brighten_screen(method)
        print("画面の自動復元が実行されました。")
    
    def cancel_auto_restore(self):
        """自動復元をキャンセル"""
        if self.auto_restore_timer:
            self.auto_restore_timer.cancel()
            self.auto_restore_timer = None
            print("画面の自動復元をキャンセルしました。")


def main():
    """テスト用のメイン関数"""
    import json
    
    # 設定を読み込み
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    controller = ScreenController(config)
    timer_controller = ScreenControllerWithTimer(controller)
    
    print("画面制御テスト:")
    print(f"システム: {controller.system}")
    
    try:
        # オーバーレイテスト
        print("\nオーバーレイテスト:")
        print("画面オーバーレイを表示中...")
        controller.darken_screen('overlay')
        time.sleep(3)
        
        print("画面オーバーレイを非表示中...")
        controller.brighten_screen('overlay')
        time.sleep(2)
        
        # 自動復元テスト
        print("\n自動復元テスト（5秒後に自動復元）:")
        timer_controller.darken_with_auto_restore('overlay', 5)
        time.sleep(6)
        
        print("テスト完了")
        
    except KeyboardInterrupt:
        print("\nテストを中断しました")
        # 画面を元に戻す
        controller.brighten_screen('overlay')
    except Exception as e:
        print(f"エラー: {e}")
        # 画面を元に戻す
        controller.brighten_screen('overlay')


if __name__ == "__main__":
    main()
