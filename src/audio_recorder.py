"""
音声録音機能
マイクで音声を録音してCMパターンとして保存する
ノイズ除去機能とマイク感度調整機能を含む
"""

import pyaudio
import wave
import os
import json
import time
from datetime import datetime
from typing import Optional, Callable
import threading


class AudioRecorder:
    """マイクで音声を録音するクラス（ノイズ除去・感度調整機能付き）"""
    
    def __init__(self, config: dict):
        self.config = config
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.recording_thread = None
        self.audio_data = []
        self.sample_rate = config['audio']['sample_rate']
        self.channels = config['audio']['channels']
        self.chunk_size = config['audio']['chunk_size']
        self.record_duration = config['audio']['record_duration']
        
    def get_audio_devices(self):
        """利用可能なオーディオデバイス一覧を取得"""
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            devices.append({
                'index': i,
                'name': device_info['name'],
                'channels': device_info['maxInputChannels'],
                'sample_rate': device_info['defaultSampleRate'],
                'is_default_input': device_info.get('isDefaultInput', False),
                'is_default_output': device_info.get('isDefaultOutput', False)
            })
        return devices
    
    def diagnose_audio_setup(self):
        """マイク設定の診断を行う"""
        print("=== マイク設定診断 ===")
        
        # デバイス一覧を取得
        devices = self.get_audio_devices()
        
        # デフォルトデバイスを確認
        try:
            default_input = self.audio.get_default_input_device_info()
            print(f"デフォルト入力デバイス: {default_input['name']}")
        except Exception as e:
            print(f"デフォルト入力デバイス取得エラー: {e}")
            return False
        
        # マイクデバイスの確認
        microphone_found = False
        for device in devices:
            device_name = device['name'].lower()
            if ('microphone' in device_name or 'mic' in device_name) and device['channels'] > 0:
                microphone_found = True
                print(f"✓ マイクデバイス: {device['name']}")
                print(f"  - チャンネル数: {device['channels']}")
                print(f"  - サンプルレート: {device['sample_rate']}")
                break
        
        if not microphone_found:
            print("⚠️  マイクデバイスが見つかりません")
            print("   システム環境設定 > セキュリティとプライバシー > プライバシー > マイク")
            print("   でアプリケーションにマイクアクセス権限を付与してください")
            return False
        
        # マイク音量テスト
        print("\n=== マイク音量テスト ===")
        try:
            mic_index = self.find_microphone_device()
            device_info = self.audio.get_device_info_by_index(mic_index)
            print(f"テスト対象マイク: {device_info['name']}")
            
            # 短時間のテスト録音
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                input_device_index=mic_index,
                frames_per_buffer=1024
            )
            
            print("3秒間のマイクテストを実行します...")
            max_level = 0.0
            for i in range(30):  # 3秒間
                data = stream.read(1024, exception_on_overflow=False)
                level = self._calculate_audio_level(data)
                max_level = max(max_level, level)
                if i % 10 == 0:
                    print(f"  時間 {i//10 + 1}秒: 音声レベル = {level:.4f}")
            
            stream.stop_stream()
            stream.close()
            
            print(f"最大音声レベル: {max_level:.4f}")
            if max_level > 0.001:
                print("✓ マイクが正常に動作しています")
            else:
                print("⚠️  マイクから音声が検出されませんでした")
                print("   マイクの音量設定を確認してください")
                return False
                
        except Exception as e:
            print(f"マイクテストエラー: {e}")
            return False
        
        print("=== 診断完了 ===")
        return microphone_found
    
    def find_microphone_device(self):
        """マイクデバイスを検索"""
        devices = self.get_audio_devices()
        
        # マイクデバイスを検索
        for device in devices:
            device_name = device['name'].lower()
            if ('microphone' in device_name or 'mic' in device_name) and device['channels'] > 0:
                print(f"✓ マイクデバイスを発見: {device['name']} (チャンネル: {device['channels']})")
                return device['index']
        
        # デフォルトの入力デバイスを使用
        default_device = self.audio.get_default_input_device_info()['index']
        print(f"デフォルトの入力デバイスを使用: {devices[default_device]['name']}")
        return default_device
    
    def start_recording(self, callback: Optional[Callable] = None):
        """録音を開始"""
        if self.is_recording:
            return False
            
        try:
            # マイクデバイスを取得
            device_index = self.find_microphone_device()
            
            # デバイスのサポートするチャンネル数を確認
            device_info = self.audio.get_device_info_by_index(device_index)
            max_channels = device_info['maxInputChannels']
            device_name = device_info['name']
            
            print(f"録音デバイス: {device_name}")
            print(f"デバイスサポートチャンネル数: {max_channels}")
            print(f"設定チャンネル数: {self.channels}")
            
            # 設定されたチャンネル数がデバイスでサポートされているかチェック
            actual_channels = min(self.channels, max_channels)
            if actual_channels != self.channels:
                print(f"⚠️  警告: デバイスは{max_channels}チャンネルまでサポートしています。{actual_channels}チャンネルで録音します。")
            
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
            print(f"✓ 録音開始: {actual_channels}チャンネル, {self.sample_rate}Hz")
            
            self.is_recording = True
            self.audio_data = []
            
            # 録音スレッドを開始
            self.recording_thread = threading.Thread(
                target=self._recording_loop,
                args=(callback,)
            )
            self.recording_thread.start()
            
            return True
            
        except Exception as e:
            print(f"録音開始エラー: {e}")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """録音を停止してファイルに保存"""
        if not self.is_recording:
            return None
            
        self.is_recording = False
        
        # 録音スレッドの終了を待つ
        if self.recording_thread:
            self.recording_thread.join()
        
        # ストリームを閉じる
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # 音声データをファイルに保存
        if self.audio_data:
            return self._save_audio_data()
        
        return None
    
    def _recording_loop(self, callback: Optional[Callable] = None):
        """録音ループ（別スレッドで実行）"""
        start_time = time.time()
        chunk_count = 0
        silent_chunks = 0
        
        while self.is_recording:
            try:
                # 音声データを読み取り
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # マイク感度調整を適用
                data = self.apply_microphone_gain(data)
                
                # ノイズ除去を適用
                data = self.apply_noise_reduction(data)
                
                self.audio_data.append(data)
                
                # 音声レベルを監視
                chunk_count += 1
                audio_level = self._calculate_audio_level(data)
                
                if audio_level < 0.001:  # 無音レベル
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                
                # 5秒ごとに音声レベルを報告
                if chunk_count % 50 == 0:  # 約5秒（50チャンク）
                    elapsed = time.time() - start_time
                    print(f"録音中... {elapsed:.1f}秒, 音声レベル: {audio_level:.4f}, 無音チャンク: {silent_chunks}")
                
                # 長時間無音の場合は警告
                if silent_chunks > 100:  # 約10秒間無音
                    print("⚠️  警告: 長時間無音が検出されています。オーディオ設定を確認してください。")
                    print("   - BlackHoleの設定を確認")
                    print("   - マルチ出力デバイスが正しく設定されているか確認")
                    print("   - システム音量が適切に設定されているか確認")
                
                # コールバック関数を呼び出し（リアルタイム処理用）
                if callback:
                    callback(data)
                
                # 最大録音時間をチェック
                if time.time() - start_time > self.record_duration:
                    break
                    
            except Exception as e:
                print(f"録音エラー: {e}")
                break
        
        # 録音終了時の統計
        total_chunks = len(self.audio_data)
        print(f"録音完了: {total_chunks}チャンク, 無音チャンク: {silent_chunks}")
    
    def _calculate_audio_level(self, audio_data: bytes) -> float:
        """音声データのレベルを計算"""
        try:
            import numpy as np
            # バイトデータをnumpy配列に変換
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            # RMS（Root Mean Square）を計算
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            # 0-1の範囲に正規化
            return rms / 32768.0
        except Exception as e:
            print(f"音声レベル計算エラー: {e}")
            return 0.0
    
    def apply_noise_reduction(self, audio_data: bytes) -> bytes:
        """音声データからノイズを除去"""
        import numpy as np
        from scipy import signal
        
        if not self.config['audio'].get('noise_reduction_enabled', True):
            return audio_data
        
        # バイトデータをnumpy配列に変換
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        
        # ノイズ閾値以下の音を減衰
        noise_threshold = self.config['audio'].get('noise_threshold', 0.02) * 32768.0
        audio_array = np.where(np.abs(audio_array) < noise_threshold, 
                               audio_array * 0.1, audio_array)
        
        # ハイパスフィルタを適用（低周波ノイズを除去）
        b, a = signal.butter(4, 100, 'high', fs=self.sample_rate)
        filtered = signal.filtfilt(b, a, audio_array)
        
        return filtered.astype(np.int16).tobytes()
    
    def apply_microphone_gain(self, audio_data: bytes) -> bytes:
        """マイク感度を調整"""
        import numpy as np
        
        gain = self.config['audio'].get('microphone_gain', 2.0)
        if gain == 1.0:
            return audio_data
        
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        audio_array = audio_array * gain
        audio_array = np.clip(audio_array, -32768, 32767)
        
        return audio_array.astype(np.int16).tobytes()
    
    def _save_audio_data(self) -> str:
        """録音した音声データをWAVファイルに保存"""
        # ファイル名を生成（タイムスタンプ付き）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cm_pattern_{timestamp}.wav"
        filepath = os.path.join("data", "cm_patterns", filename)
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # 実際に使用したチャンネル数を取得（フォールバック）
        channels_to_use = getattr(self, 'actual_channels', self.channels)
        
        # WAVファイルに保存
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(channels_to_use)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.audio_data))
        
        # メタデータを保存
        metadata = {
            'filename': filename,
            'timestamp': timestamp,
            'sample_rate': self.sample_rate,
            'channels': channels_to_use,
            'duration': len(self.audio_data) * self.chunk_size / self.sample_rate,
            'file_size': os.path.getsize(filepath)
        }
        
        metadata_file = filepath.replace('.wav', '.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"CMパターンを保存しました: {filepath}")
        return filepath
    
    def cleanup(self):
        """リソースをクリーンアップ"""
        if self.is_recording:
            self.stop_recording()
        
        if self.audio:
            self.audio.terminate()


def main():
    """テスト用のメイン関数"""
    # 設定を読み込み
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    recorder = AudioRecorder(config)
    
    try:
        print("利用可能なオーディオデバイス:")
        devices = recorder.get_audio_devices()
        for device in devices:
            print(f"  {device['index']}: {device['name']} (チャンネル: {device['channels']})")
        
        print(f"\nシステム音声デバイス: {recorder.find_system_audio_device()}")
        
        input("\nEnterキーを押すと録音を開始します...")
        
        if recorder.start_recording():
            print("録音中... (Ctrl+Cで停止)")
            try:
                while recorder.is_recording:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
            
            filepath = recorder.stop_recording()
            if filepath:
                print(f"録音完了: {filepath}")
            else:
                print("録音に失敗しました")
        
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        recorder.cleanup()


if __name__ == "__main__":
    main()
