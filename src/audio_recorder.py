"""
音声録音機能
システム音声（再生中の音）をキャプチャしてCMパターンとして保存する
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
    """システム音声を録音するクラス"""
    
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
                'sample_rate': device_info['defaultSampleRate']
            })
        return devices
    
    def find_system_audio_device(self):
        """システム音声（ループバック）デバイスを検索"""
        devices = self.get_audio_devices()
        
        # 優先順位付きでシステム音声をキャプチャするデバイスを探す
        priority_keywords = [
            'blackhole',  # 最優先
            'loopback',   # 次に優先
            'soundflower', 'multi-output', 'aggregate'
        ]
        
        # 優先順位の高いデバイスから検索
        for keyword in priority_keywords:
            for device in devices:
                device_name = device['name'].lower()
                if keyword in device_name:
                    print(f"✓ システム音声デバイスを発見: {device['name']} (キーワード: {keyword})")
                    return device['index']
        
        # その他のシステム音声デバイスを検索
        for device in devices:
            device_name = device['name'].lower()
            if any(keyword in device_name for keyword in [
                'system', 'stereo mix', 'what u hear'
            ]):
                print(f"✓ システム音声デバイスを発見: {device['name']}")
                return device['index']
        
        # システム音声デバイスが見つからない場合の警告
        print("⚠️  警告: システム音声をキャプチャできるデバイスが見つかりません")
        print("   現在のデバイス一覧:")
        for device in devices:
            print(f"     {device['index']}: {device['name']} (チャンネル: {device['channels']})")
        print("\n   システム音声を録音するには、以下のいずれかをインストールしてください:")
        print("   - BlackHole: brew install blackhole-2ch")
        print("   - Loopback: https://rogueamoeba.com/loopback/")
        print("   - Soundflower: https://github.com/mattingalls/Soundflower")
        print("\n   インストール後、Audio MIDI Setupでマルチ出力デバイスを設定してください。")
        
        # デフォルトの入力デバイスを使用（警告付き）
        default_device = self.audio.get_default_input_device_info()['index']
        print(f"   デフォルトの入力デバイスを使用します: {devices[default_device]['name']}")
        return default_device
    
    def start_recording(self, callback: Optional[Callable] = None):
        """録音を開始"""
        if self.is_recording:
            return False
            
        try:
            # システム音声デバイスを取得
            device_index = self.find_system_audio_device()
            
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
        
        while self.is_recording:
            try:
                # 音声データを読み取り
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_data.append(data)
                
                # コールバック関数を呼び出し（リアルタイム処理用）
                if callback:
                    callback(data)
                
                # 最大録音時間をチェック
                if time.time() - start_time > self.record_duration:
                    break
                    
            except Exception as e:
                print(f"録音エラー: {e}")
                break
    
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
