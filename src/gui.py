"""
GUIインターフェース
Tkinterを使用したメインアプリケーション画面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import json
import os
from typing import Optional, Dict, Any

from audio_recorder import AudioRecorder
from audio_monitor import AudioMonitor
from system_controller import SystemController, VolumeController
from screen_controller import ScreenController, ScreenControllerWithTimer


class CMMuterGUI:
    """CMミュート・暗転ツールのメインGUIクラス"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Abema TV CM Muter")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # 設定を読み込み
        self.config = self._load_config()
        
        # コンポーネントを初期化
        self.audio_recorder = AudioRecorder(self.config)
        self.audio_monitor = AudioMonitor(self.config)
        self.system_controller = SystemController(self.config)
        self.screen_controller = ScreenController(self.config)
        
        # ヘルパークラス
        self.volume_controller = VolumeController(self.system_controller)
        self.screen_timer_controller = ScreenControllerWithTimer(self.screen_controller)
        
        # 状態変数
        self.is_recording = False
        self.is_monitoring = False
        self.cm_detected = False
        
        # GUI要素を作成
        self._create_widgets()
        self._setup_callbacks()
        
        # 状態更新タイマー
        self._start_status_update()
    
    def _load_config(self) -> dict:
        """設定ファイルを読み込み"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """デフォルト設定を取得"""
        return {
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
    
    def _create_widgets(self):
        """GUI要素を作成"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="Abema TV CM Muter", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # CMパターン録音セクション
        self._create_recording_section(main_frame, 1)
        
        # 音声監視セクション
        self._create_monitoring_section(main_frame, 2)
        
        # 設定セクション
        self._create_settings_section(main_frame, 3)
        
        # 状態表示セクション
        self._create_status_section(main_frame, 4)
        
        # ボタンセクション
        self._create_button_section(main_frame, 5)
        
        # グリッドの重みを設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def _create_recording_section(self, parent, row):
        """録音セクションを作成"""
        # 録音フレーム
        recording_frame = ttk.LabelFrame(parent, text="CMパターン録音", padding="10")
        recording_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 録音ボタン
        self.record_button = ttk.Button(
            recording_frame, 
            text="録音開始", 
            command=self._toggle_recording
        )
        self.record_button.grid(row=0, column=0, padx=(0, 10))
        
        # 録音状態ラベル
        self.recording_status_label = ttk.Label(recording_frame, text="停止中")
        self.recording_status_label.grid(row=0, column=1)
        
        # 録音時間表示
        self.recording_time_label = ttk.Label(recording_frame, text="00:00")
        self.recording_time_label.grid(row=0, column=2, padx=(10, 0))
    
    def _create_monitoring_section(self, parent, row):
        """監視セクションを作成"""
        # 監視フレーム
        monitoring_frame = ttk.LabelFrame(parent, text="音声監視", padding="10")
        monitoring_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 監視開始ボタン
        self.monitor_button = ttk.Button(
            monitoring_frame, 
            text="監視開始", 
            command=self._toggle_monitoring
        )
        self.monitor_button.grid(row=0, column=0, padx=(0, 10))
        
        # 監視状態ラベル
        self.monitoring_status_label = ttk.Label(monitoring_frame, text="停止中")
        self.monitoring_status_label.grid(row=0, column=1)
        
        # CM検出状態ラベル
        self.cm_detection_label = ttk.Label(monitoring_frame, text="CM未検出", foreground="green")
        self.cm_detection_label.grid(row=0, column=2, padx=(10, 0))
    
    def _create_settings_section(self, parent, row):
        """設定セクションを作成"""
        # 設定フレーム
        settings_frame = ttk.LabelFrame(parent, text="設定", padding="10")
        settings_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # マッチング閾値
        ttk.Label(settings_frame, text="マッチング閾値:").grid(row=0, column=0, sticky=tk.W)
        self.threshold_var = tk.DoubleVar(value=self.config['audio']['match_threshold'])
        threshold_scale = ttk.Scale(
            settings_frame, 
            from_=0.1, 
            to=1.0, 
            variable=self.threshold_var,
            command=self._update_threshold
        )
        threshold_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        self.threshold_label = ttk.Label(settings_frame, text=f"{self.config['audio']['match_threshold']:.2f}")
        self.threshold_label.grid(row=0, column=2, padx=(5, 0))
        
        # ミュート設定
        self.mute_enabled_var = tk.BooleanVar(value=True)
        mute_check = ttk.Checkbutton(
            settings_frame, 
            text="CM検出時にミュート", 
            variable=self.mute_enabled_var
        )
        mute_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # 画面暗転設定
        self.screen_darken_var = tk.BooleanVar(value=True)
        screen_check = ttk.Checkbutton(
            settings_frame, 
            text="CM検出時に画面暗転", 
            variable=self.screen_darken_var
        )
        screen_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        settings_frame.columnconfigure(1, weight=1)
    
    def _create_status_section(self, parent, row):
        """状態表示セクションを作成"""
        # 状態フレーム
        status_frame = ttk.LabelFrame(parent, text="状態", padding="10")
        status_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 音量表示
        ttk.Label(status_frame, text="現在の音量:").grid(row=0, column=0, sticky=tk.W)
        self.volume_label = ttk.Label(status_frame, text="--")
        self.volume_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # ミュート状態
        ttk.Label(status_frame, text="ミュート状態:").grid(row=1, column=0, sticky=tk.W)
        self.mute_status_label = ttk.Label(status_frame, text="--")
        self.mute_status_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        # 画面状態
        ttk.Label(status_frame, text="画面状態:").grid(row=2, column=0, sticky=tk.W)
        self.screen_status_label = ttk.Label(status_frame, text="--")
        self.screen_status_label.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))
    
    def _create_button_section(self, parent, row):
        """ボタンセクションを作成"""
        # ボタンフレーム
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0))
        
        # CMパターン管理ボタン
        ttk.Button(
            button_frame, 
            text="CMパターン管理", 
            command=self._show_pattern_manager
        ).grid(row=0, column=0, padx=(0, 10))
        
        # 設定保存ボタン
        ttk.Button(
            button_frame, 
            text="設定保存", 
            command=self._save_config
        ).grid(row=0, column=1, padx=(0, 10))
        
        # 終了ボタン
        ttk.Button(
            button_frame, 
            text="終了", 
            command=self._on_closing
        ).grid(row=0, column=2)
    
    def _setup_callbacks(self):
        """コールバック関数を設定"""
        # 音声監視のコールバック
        self.audio_monitor.set_cm_detected_callback(self._on_cm_detected)
        self.audio_monitor.set_cm_ended_callback(self._on_cm_ended)
        
        # ウィンドウクローズイベント
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _toggle_recording(self):
        """録音の開始/停止を切り替え"""
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _start_recording(self):
        """録音を開始"""
        if self.audio_recorder.start_recording():
            self.is_recording = True
            self.record_button.config(text="録音停止")
            self.recording_status_label.config(text="録音中", foreground="red")
            self._start_recording_timer()
        else:
            messagebox.showerror("エラー", "録音を開始できませんでした")
    
    def _stop_recording(self):
        """録音を停止"""
        filepath = self.audio_recorder.stop_recording()
        self.is_recording = False
        self.record_button.config(text="録音開始")
        self.recording_status_label.config(text="停止中", foreground="black")
        self.recording_time_label.config(text="00:00")
        
        if filepath:
            messagebox.showinfo("完了", f"CMパターンを保存しました:\n{filepath}")
            # 音声監視に新しいパターンを追加
            self.audio_monitor.add_cm_pattern(filepath, {})
        else:
            messagebox.showerror("エラー", "録音に失敗しました")
    
    def _start_recording_timer(self):
        """録音タイマーを開始"""
        if self.is_recording:
            start_time = time.time()
            while self.is_recording:
                elapsed = time.time() - start_time
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                self.recording_time_label.config(text=f"{minutes:02d}:{seconds:02d}")
                time.sleep(0.1)
    
    def _toggle_monitoring(self):
        """監視の開始/停止を切り替え"""
        if not self.is_monitoring:
            self._start_monitoring()
        else:
            self._stop_monitoring()
    
    def _start_monitoring(self):
        """監視を開始"""
        if self.audio_monitor.start_monitoring():
            self.is_monitoring = True
            self.monitor_button.config(text="監視停止")
            self.monitoring_status_label.config(text="監視中", foreground="blue")
        else:
            messagebox.showerror("エラー", "監視を開始できませんでした")
    
    def _stop_monitoring(self):
        """監視を停止"""
        self.audio_monitor.stop_monitoring()
        self.is_monitoring = False
        self.monitor_button.config(text="監視開始")
        self.monitoring_status_label.config(text="停止中", foreground="black")
        self.cm_detection_label.config(text="CM未検出", foreground="green")
    
    def _on_cm_detected(self, pattern, similarity):
        """CM検出時のコールバック"""
        self.cm_detected = True
        self.cm_detection_label.config(text=f"CM検出: {similarity:.2f}", foreground="red")
        
        # ミュート
        if self.mute_enabled_var.get():
            self.system_controller.mute()
        
        # 画面暗転
        if self.screen_darken_var.get():
            self.screen_controller.darken_screen('overlay')
    
    def _on_cm_ended(self, pattern, duration):
        """CM終了時のコールバック"""
        self.cm_detected = False
        self.cm_detection_label.config(text="CM未検出", foreground="green")
        
        # ミュート解除
        if self.mute_enabled_var.get():
            self.system_controller.unmute()
        
        # 画面復元
        if self.screen_darken_var.get():
            self.screen_controller.brighten_screen('overlay')
    
    def _update_threshold(self, value):
        """マッチング閾値を更新"""
        threshold = float(value)
        self.threshold_label.config(text=f"{threshold:.2f}")
        self.audio_monitor.update_match_threshold(threshold)
    
    def _start_status_update(self):
        """状態更新タイマーを開始"""
        self._update_status()
        self.root.after(1000, self._start_status_update)  # 1秒ごとに更新
    
    def _update_status(self):
        """状態表示を更新"""
        # 音量
        volume = self.system_controller.get_volume()
        if volume is not None:
            self.volume_label.config(text=f"{volume:.1%}")
        else:
            self.volume_label.config(text="--")
        
        # ミュート状態
        is_muted = self.system_controller.get_mute_status()
        self.mute_status_label.config(
            text="ミュート中" if is_muted else "通常",
            foreground="red" if is_muted else "green"
        )
        
        # 画面状態
        screen_status = self.screen_controller.get_screen_status()
        is_darkened = screen_status['is_darkened']
        self.screen_status_label.config(
            text="暗転中" if is_darkened else "通常",
            foreground="red" if is_darkened else "green"
        )
    
    def _show_pattern_manager(self):
        """CMパターン管理画面を表示"""
        patterns = self.audio_monitor.get_cm_patterns()
        
        # 新しいウィンドウを作成
        pattern_window = tk.Toplevel(self.root)
        pattern_window.title("CMパターン管理")
        pattern_window.geometry("500x400")
        
        # パターン一覧
        frame = ttk.Frame(pattern_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="保存されたCMパターン:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # リストボックス
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        listbox = tk.Listbox(listbox_frame)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # パターンをリストに追加
        for name, data in patterns.items():
            duration = data['metadata'].get('duration', 0)
            listbox.insert(tk.END, f"{name} ({duration:.1f}秒)")
        
        # ボタン
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="削除", 
            command=lambda: self._delete_pattern(listbox, patterns)
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="閉じる", 
            command=pattern_window.destroy
        ).pack(side=tk.RIGHT)
    
    def _delete_pattern(self, listbox, patterns):
        """選択されたパターンを削除"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "削除するパターンを選択してください")
            return
        
        index = selection[0]
        pattern_names = list(patterns.keys())
        pattern_name = pattern_names[index]
        
        if messagebox.askyesno("確認", f"'{pattern_name}'を削除しますか？"):
            if self.audio_monitor.remove_cm_pattern(pattern_name):
                listbox.delete(index)
                messagebox.showinfo("完了", "パターンを削除しました")
            else:
                messagebox.showerror("エラー", "パターンの削除に失敗しました")
    
    def _save_config(self):
        """設定を保存"""
        try:
            # 現在の設定を更新
            self.config['audio']['match_threshold'] = self.threshold_var.get()
            
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("完了", "設定を保存しました")
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました:\n{e}")
    
    def _on_closing(self):
        """アプリケーション終了時の処理"""
        # 監視を停止
        if self.is_monitoring:
            self._stop_monitoring()
        
        # 録音を停止
        if self.is_recording:
            self._stop_recording()
        
        # リソースをクリーンアップ
        self.audio_recorder.cleanup()
        self.audio_monitor.cleanup()
        
        # ウィンドウを閉じる
        self.root.destroy()
    
    def run(self):
        """アプリケーションを実行"""
        self.root.mainloop()


def main():
    """メイン関数"""
    try:
        app = CMMuterGUI()
        app.run()
    except Exception as e:
        print(f"アプリケーションエラー: {e}")
        messagebox.showerror("エラー", f"アプリケーションの起動に失敗しました:\n{e}")


if __name__ == "__main__":
    main()
