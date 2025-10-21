"""
音声マッチング機能
pyacoustidを使用して音声フィンガープリントを生成・比較する
"""

import os
import json
import numpy as np
import librosa
import acoustid
from typing import List, Dict, Tuple, Optional
import threading
from concurrent.futures import ThreadPoolExecutor


class AudioMatcher:
    """音声パターンマッチングクラス"""
    
    def __init__(self, config: dict):
        self.config = config
        self.cm_patterns = {}  # 保存されたCMパターン
        self.match_threshold = config['audio']['match_threshold']
        self.silence_threshold = config['audio']['silence_threshold']
        self.sample_rate = config['audio']['sample_rate']
        self.chunk_size = config['audio']['chunk_size']
        
        # CMパターンを読み込み
        self._load_cm_patterns()
    
    def _load_cm_patterns(self):
        """保存されたCMパターンを読み込み"""
        patterns_dir = "data/cm_patterns"
        if not os.path.exists(patterns_dir):
            return
        
        for filename in os.listdir(patterns_dir):
            if filename.endswith('.json'):
                try:
                    metadata_file = os.path.join(patterns_dir, filename)
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    # 対応するWAVファイルのパス
                    wav_file = metadata_file.replace('.json', '.wav')
                    if os.path.exists(wav_file):
                        # 音声フィンガープリントを生成
                        fingerprint = self._generate_fingerprint(wav_file)
                        if fingerprint:
                            self.cm_patterns[metadata['filename']] = {
                                'metadata': metadata,
                                'fingerprint': fingerprint,
                                'filepath': wav_file
                            }
                            print(f"CMパターンを読み込みました: {metadata['filename']}")
                
                except Exception as e:
                    print(f"CMパターン読み込みエラー ({filename}): {e}")
    
    def _generate_fingerprint(self, audio_file: str) -> Optional[str]:
        """音声ファイルからフィンガープリントを生成"""
        try:
            # acoustidを使用してフィンガープリントを生成
            fingerprint, duration = acoustid.fingerprint_file(audio_file)
            return fingerprint
        except Exception as e:
            print(f"フィンガープリント生成エラー ({audio_file}): {e}")
            return None
    
    def _generate_fingerprint_from_data(self, audio_data: bytes) -> Optional[str]:
        """音声データからフィンガープリントを生成"""
        try:
            # 一時ファイルに保存してからフィンガープリントを生成
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                fingerprint, duration = acoustid.fingerprint_file(temp_file.name)
                
                # 一時ファイルを削除
                os.unlink(temp_file.name)
                
                return fingerprint
        except Exception as e:
            print(f"音声データからフィンガープリント生成エラー: {e}")
            return None
    
    def _calculate_similarity(self, fingerprint1: str, fingerprint2: str) -> float:
        """2つのフィンガープリントの類似度を計算"""
        try:
            # acoustidのcompare_fingerprints関数を使用して類似度を計算
            # 戻り値は0-1の範囲（1が完全一致）
            similarity = acoustid.compare_fingerprints(fingerprint1, fingerprint2)
            return similarity
        except Exception as e:
            print(f"類似度計算エラー: {e}")
            return 0.0
    
    def _is_silence(self, audio_data: np.ndarray) -> bool:
        """音声データが無音かどうかを判定"""
        # RMS（Root Mean Square）を計算
        rms = np.sqrt(np.mean(audio_data**2))
        return rms < self.silence_threshold
    
    def match_audio(self, audio_data: bytes) -> Tuple[bool, Optional[Dict], float]:
        """
        音声データがCMパターンと一致するかチェック
        
        Args:
            audio_data: 音声データ（バイト列）
            
        Returns:
            (is_match, matched_pattern, similarity_score)
        """
        try:
            # 音声データからフィンガープリントを生成
            current_fingerprint = self._generate_fingerprint_from_data(audio_data)
            if not current_fingerprint:
                return False, None, 0.0
            
            # 保存されたCMパターンと比較
            best_match = None
            best_similarity = 0.0
            
            for pattern_name, pattern_data in self.cm_patterns.items():
                similarity = self._calculate_similarity(
                    current_fingerprint,
                    pattern_data['fingerprint']
                )
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = pattern_data
            
            # 閾値を超えている場合はマッチ
            is_match = best_similarity >= self.match_threshold
            
            return is_match, best_match, best_similarity
            
        except Exception as e:
            print(f"音声マッチングエラー: {e}")
            return False, None, 0.0
    
    def match_audio_realtime(self, audio_chunk: bytes) -> Tuple[bool, Optional[Dict], float]:
        """
        リアルタイム音声マッチング（短いチャンク用）
        
        Args:
            audio_chunk: 音声チャンク（バイト列）
            
        Returns:
            (is_match, matched_pattern, similarity_score)
        """
        try:
            # 音声データをnumpy配列に変換
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            
            # 無音チェック
            if self._is_silence(audio_array):
                return False, None, 0.0
            
            # フィンガープリント生成とマッチング
            return self.match_audio(audio_chunk)
            
        except Exception as e:
            print(f"リアルタイムマッチングエラー: {e}")
            return False, None, 0.0
    
    def add_cm_pattern(self, audio_file: str, metadata: Dict) -> bool:
        """新しいCMパターンを追加"""
        try:
            fingerprint = self._generate_fingerprint(audio_file)
            if fingerprint:
                self.cm_patterns[metadata['filename']] = {
                    'metadata': metadata,
                    'fingerprint': fingerprint,
                    'filepath': audio_file
                }
                print(f"CMパターンを追加しました: {metadata['filename']}")
                return True
            return False
        except Exception as e:
            print(f"CMパターン追加エラー: {e}")
            return False
    
    def remove_cm_pattern(self, pattern_name: str) -> bool:
        """CMパターンを削除"""
        if pattern_name in self.cm_patterns:
            del self.cm_patterns[pattern_name]
            print(f"CMパターンを削除しました: {pattern_name}")
            return True
        return False
    
    def get_cm_patterns(self) -> Dict:
        """保存されたCMパターン一覧を取得"""
        return {
            name: {
                'metadata': data['metadata'],
                'filepath': data['filepath']
            }
            for name, data in self.cm_patterns.items()
        }
    
    def update_threshold(self, new_threshold: float):
        """マッチング閾値を更新"""
        self.match_threshold = new_threshold
        print(f"マッチング閾値を更新しました: {new_threshold}")


def main():
    """テスト用のメイン関数"""
    # 設定を読み込み
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    matcher = AudioMatcher(config)
    
    print("読み込まれたCMパターン:")
    patterns = matcher.get_cm_patterns()
    for name, data in patterns.items():
        print(f"  - {name}: {data['metadata']['duration']:.1f}秒")
    
    # テスト用の音声ファイルがある場合
    test_file = "data/cm_patterns/cm_pattern_20240101_120000.wav"
    if os.path.exists(test_file):
        print(f"\nテストファイルでマッチング: {test_file}")
        with open(test_file, 'rb') as f:
            audio_data = f.read()
        
        is_match, matched_pattern, similarity = matcher.match_audio(audio_data)
        print(f"マッチ結果: {is_match}")
        if matched_pattern:
            print(f"マッチしたパターン: {matched_pattern['metadata']['filename']}")
        print(f"類似度: {similarity:.3f}")


if __name__ == "__main__":
    main()
