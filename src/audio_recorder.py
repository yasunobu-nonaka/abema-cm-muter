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
        """オーディオ設定の診断を行う"""
        print("=== オーディオ設定診断 ===")
        
        # デバイス一覧を取得
        devices = self.get_audio_devices()
        
        # デフォルトデバイスを確認
        try:
            default_input = self.audio.get_default_input_device_info()
            default_output = self.audio.get_default_output_device_info()
            print(f"デフォルト入力デバイス: {default_input['name']}")
            print(f"デフォルト出力デバイス: {default_output['name']}")
        except Exception as e:
            print(f"デフォルトデバイス取得エラー: {e}")
        
        # BlackHoleの状態を確認
        blackhole_found = False
        for device in devices:
            if 'blackhole' in device['name'].lower():
                blackhole_found = True
                print(f"BlackHoleデバイス: {device['name']}")
                print(f"  - チャンネル数: {device['channels']}")
                print(f"  - サンプルレート: {device['sample_rate']}")
                break
        
        if not blackhole_found:
            print("⚠️  BlackHoleデバイスが見つかりません")
            print("   以下のコマンドでインストールしてください:")
            print("   brew install blackhole-2ch")
        
        # Aggregate Deviceの確認
        aggregate_found = False
        for device in devices:
            if 'aggregate' in device['name'].lower():
                aggregate_found = True
                print(f"Aggregate Device: {device['name']}")
                break
        
        if not aggregate_found:
            print("⚠️  Aggregate Deviceが見つかりません")
            print("   Audio MIDI SetupでAggregate Deviceを作成してください")
        
        # システム出力デバイスの確認
        try:
            default_output = self.audio.get_default_output_device_info()
            if 'aggregate' not in default_output['name'].lower():
                print("⚠️  システム出力デバイスがAggregate Deviceに設定されていません")
                print(f"   現在の出力デバイス: {default_output['name']}")
                print("   以下の手順で設定を変更してください:")
                print("   1. システム環境設定 > サウンド > 出力")
                print("   2. 'Aggregate Device'を選択")
                print("   3. アプリケーションを再起動")
                return False
            else:
                print(f"✓ システム出力デバイス: {default_output['name']}")
        except Exception as e:
            print(f"出力デバイス確認エラー: {e}")
            return False
        
        # Aggregate Deviceの詳細設定を確認
        if aggregate_found:
            print("\n=== Aggregate Device詳細確認 ===")
            try:
                # Aggregate Deviceのインデックスを取得
                aggregate_index = None
                for device in devices:
                    if 'aggregate' in device['name'].lower():
                        aggregate_index = device['index']
                        break
                
                if aggregate_index is not None:
                    # Aggregate Deviceの詳細情報を取得
                    aggregate_info = self.audio.get_device_info_by_index(aggregate_index)
                    print(f"Aggregate Device詳細:")
                    print(f"  - 名前: {aggregate_info['name']}")
                    print(f"  - 入力チャンネル: {aggregate_info['maxInputChannels']}")
                    print(f"  - 出力チャンネル: {aggregate_info['maxOutputChannels']}")
                    print(f"  - サンプルレート: {aggregate_info['defaultSampleRate']}")
                    
                    # Aggregate Deviceが入力デバイスとして使用可能かチェック
                    if aggregate_info['maxInputChannels'] > 0:
                        print("  ✓ Aggregate Deviceは入力として使用可能")
                    else:
                        print("  ⚠️  Aggregate Deviceは入力として使用できません")
                        print("     Audio MIDI SetupでAggregate Deviceの設定を確認してください")
                        return False
                        
            except Exception as e:
                print(f"Aggregate Device詳細確認エラー: {e}")
                return False
        
        print("=== 診断完了 ===")
        return blackhole_found and aggregate_found
    
    def find_system_audio_device(self):
        """システム音声（ループバック）デバイスを検索"""
        devices = self.get_audio_devices()
        
        # BlackHoleを最優先で検索（入力チャンネルがあることを確認）
        for device in devices:
            device_name = device['name'].lower()
            if 'blackhole' in device_name and device['channels'] > 0:
                print(f"✓ システム音声デバイスを発見: {device['name']} (チャンネル: {device['channels']})")
                return device['index']
        
        # その他のループバックデバイスを検索
        priority_keywords = [
            'aggregate', 'loopback', 'soundflower', 'multi-output'
        ]
        
        for keyword in priority_keywords:
            for device in devices:
                device_name = device['name'].lower()
                if keyword in device_name and device['channels'] > 0:
                    print(f"✓ システム音声デバイスを発見: {device['name']} (キーワード: {keyword}, チャンネル: {device['channels']})")
                    return device['index']
        
        # その他のシステム音声デバイスを検索
        for device in devices:
            device_name = device['name'].lower()
            if any(keyword in device_name for keyword in [
                'system', 'stereo mix', 'what u hear'
            ]) and device['channels'] > 0:
                print(f"✓ システム音声デバイスを発見: {device['name']} (チャンネル: {device['channels']})")
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
