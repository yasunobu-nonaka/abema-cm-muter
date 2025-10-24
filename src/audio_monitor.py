"""
リアルタイム音声監視機能
システム音声を常時監視してCMを検出する
"""

import pyaudio
import threading
import time
from typing import Callable, Optional
from audio_recorder import AudioRecorder
from audio_matcher import AudioMatcher


class AudioMonitor:
    """リアルタイム音声監視クラス"""
    
    def __init__(self, config: dict):
        self.config = config
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # 音声処理コンポーネント
        self.recorder = AudioRecorder(config)
        self.matcher = AudioMatcher(config)
        
        # コールバック関数
        self.cm_detected_callback: Optional[Callable] = None
        self.cm_ended_callback: Optional[Callable] = None
        
        # 監視設定
        self.sample_rate = config['audio']['sample_rate']
        self.channels = config['audio']['channels']
        self.chunk_size = config['audio']['chunk_size']
        
        # CM検出状態
        self.cm_detected = False
        self.current_cm_pattern = None
        self.cm_start_time = None
        self.last_detection_time = 0
        
        # バッファリング（複数チャンクを結合してマッチング）
        self.audio_buffer = []
        self.buffer_size = 10  # 10チャンク分のバッファ
        self.buffer_lock = threading.Lock()
    
    def set_cm_detected_callback(self, callback: Callable):
        """CM検出時のコールバック関数を設定"""
        self.cm_detected_callback = callback
    
    def set_cm_ended_callback(self, callback: Callable):
        """CM終了時のコールバック関数を設定"""
        self.cm_ended_callback = callback
    
    def start_monitoring(self) -> bool:
        """音声監視を開始"""
        if self.is_monitoring:
            return False
        
        try:
            # システム音声デバイスを取得
            device_index = self.recorder.find_system_audio_device()
            
            # デバイスのサポートするチャンネル数を確認
            device_info = self.audio.get_device_info_by_index(device_index)
            max_channels = device_info['maxInputChannels']
            device_name = device_info['name']
            
            print(f"監視デバイス: {device_name}")
            print(f"デバイスサポートチャンネル数: {max_channels}")
            print(f"設定チャンネル数: {self.channels}")
            
            # 設定されたチャンネル数がデバイスでサポートされているかチェック
            actual_channels = min(self.channels, max_channels)
            if actual_channels != self.channels:
                print(f"⚠️  警告: デバイスは{max_channels}チャンネルまでサポートしています。{actual_channels}チャンネルで監視します。")
            
            # オーディオストリームを開く
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=actual_channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size
            )
            
            # 実際に使用するチャンネル数を保存
            self.actual_channels = actual_channels
            print(f"✓ 監視開始: {actual_channels}チャンネル, {self.sample_rate}Hz")
            
            self.is_monitoring = True
            self.audio_buffer = []
            
            # 監視スレッドを開始
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.start()
            
            print("音声監視を開始しました")
            return True
            
        except Exception as e:
            print(f"監視開始エラー: {e}")
            return False
    
    def stop_monitoring(self):
        """音声監視を停止"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        # 監視スレッドの終了を待つ
        if self.monitoring_thread:
            self.monitoring_thread.join()
        
        # ストリームを閉じる
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        print("音声監視を停止しました")
    
    def _monitoring_loop(self):
        """監視ループ（別スレッドで実行）"""
        while self.is_monitoring:
            try:
                # 音声データを読み取り
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # マイク感度調整を適用
                data = self.recorder.apply_microphone_gain(data)
                
                # ノイズ除去を適用
                data = self.recorder.apply_noise_reduction(data)
                
                # バッファに追加
                with self.buffer_lock:
                    self.audio_buffer.append(data)
                    
                    # バッファサイズを超えた場合は古いデータを削除
                    if len(self.audio_buffer) > self.buffer_size:
                        self.audio_buffer.pop(0)
                    
                    # 十分なデータが蓄積されたらマッチングを実行
                    if len(self.audio_buffer) >= self.buffer_size:
                        self._process_audio_buffer()
                
            except Exception as e:
                print(f"監視エラー: {e}")
                time.sleep(0.1)
    
    def _process_audio_buffer(self):
        """音声バッファを処理してCM検出を行う"""
        try:
            # バッファの音声データを結合
            combined_data = b''.join(self.audio_buffer)
            
            # CMマッチングを実行
            is_match, matched_pattern, similarity = self.matcher.match_audio_realtime(combined_data)
            
            current_time = time.time()
            
            if is_match and matched_pattern:
                # CMが検出された場合
                if not self.cm_detected:
                    # 新しいCMの開始
                    self.cm_detected = True
                    self.current_cm_pattern = matched_pattern
                    self.cm_start_time = current_time
                    
                    print(f"CM検出: {matched_pattern['metadata']['filename']} (類似度: {similarity:.3f})")
                    
                    # コールバック関数を呼び出し
                    if self.cm_detected_callback:
                        self.cm_detected_callback(matched_pattern, similarity)
                
                self.last_detection_time = current_time
            
            else:
                # CMが検出されない場合
                if self.cm_detected:
                    # CM終了の判定（一定時間CMが検出されない場合）
                    if current_time - self.last_detection_time > 2.0:  # 2秒間CMが検出されない
                        self._end_cm_detection()
            
        except Exception as e:
            print(f"音声バッファ処理エラー: {e}")
    
    def _end_cm_detection(self):
        """CM検出を終了"""
        if self.cm_detected:
            duration = time.time() - self.cm_start_time if self.cm_start_time else 0
            
            print(f"CM終了: {self.current_cm_pattern['metadata']['filename']} (継続時間: {duration:.1f}秒)")
            
            # コールバック関数を呼び出し
            if self.cm_ended_callback:
                self.cm_ended_callback(self.current_cm_pattern, duration)
            
            # 状態をリセット
            self.cm_detected = False
            self.current_cm_pattern = None
            self.cm_start_time = None
    
    def get_monitoring_status(self) -> dict:
        """監視状態を取得"""
        return {
            'is_monitoring': self.is_monitoring,
            'cm_detected': self.cm_detected,
            'current_cm_pattern': self.current_cm_pattern['metadata']['filename'] if self.current_cm_pattern else None,
            'cm_duration': time.time() - self.cm_start_time if self.cm_start_time else 0,
            'buffer_size': len(self.audio_buffer)
        }
    
    def add_cm_pattern(self, audio_file: str, metadata: dict) -> bool:
        """新しいCMパターンを追加"""
        return self.matcher.add_cm_pattern(audio_file, metadata)
    
    def remove_cm_pattern(self, pattern_name: str) -> bool:
        """CMパターンを削除"""
        return self.matcher.remove_cm_pattern(pattern_name)
    
    def get_cm_patterns(self) -> dict:
        """保存されたCMパターン一覧を取得"""
        return self.matcher.get_cm_patterns()
    
    def update_match_threshold(self, threshold: float):
        """マッチング閾値を更新"""
        self.matcher.update_threshold(threshold)
    
    def cleanup(self):
        """リソースをクリーンアップ"""
        self.stop_monitoring()
        
        if self.audio:
            self.audio.terminate()
        
        self.recorder.cleanup()


def main():
    """テスト用のメイン関数"""
    import json
    
    # 設定を読み込み
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    monitor = AudioMonitor(config)
    
    # コールバック関数を設定
    def on_cm_detected(pattern, similarity):
        print(f"🎵 CM検出: {pattern['metadata']['filename']} (類似度: {similarity:.3f})")
    
    def on_cm_ended(pattern, duration):
        print(f"🔇 CM終了: {pattern['metadata']['filename']} (継続時間: {duration:.1f}秒)")
    
    monitor.set_cm_detected_callback(on_cm_detected)
    monitor.set_cm_ended_callback(on_cm_ended)
    
    try:
        print("音声監視を開始します...")
        if monitor.start_monitoring():
            print("監視中... (Ctrl+Cで停止)")
            
            # 監視状態を定期的に表示
            while monitor.is_monitoring:
                time.sleep(5)
                status = monitor.get_monitoring_status()
                print(f"監視状態: {status}")
        
    except KeyboardInterrupt:
        print("\n監視を停止します...")
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        monitor.cleanup()


if __name__ == "__main__":
    main()
