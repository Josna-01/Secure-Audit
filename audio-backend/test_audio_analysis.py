import io
import math
import struct
import unittest
import wave

import numpy as np
from app import analyze_audio_bytes, _decode_audio_to_mono_pcm


class AudioAnalysisTests(unittest.TestCase):
    def _make_wav_bytes(
        self,
        *,
        amplitude: float = 0.4,
        sample_rate: int = 16000,
        duration_seconds: float = 4.0,
        insert_silence: bool = False,
        insert_noise_discontinuity: bool = False,
    ) -> bytes:
        total_frames = int(sample_rate * duration_seconds)
        frames = bytearray()
        for index in range(total_frames):
            if insert_silence and (total_frames // 3) <= index < (total_frames // 3 + int(sample_rate * 0.45)):
                sample_value = 0
            elif insert_noise_discontinuity and (total_frames // 2) <= index < (total_frames // 2 + int(sample_rate * 0.45)):
                sample_value = int(32767 * (0.9 * (hash(index) % 1000) / 1000.0 - 0.45))
            else:
                sample_value = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", sample_value))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)
        return buffer.getvalue()

    def test_decode_wav_samples(self) -> None:
        payload = self._make_wav_bytes(duration_seconds=1.0)
        samples, sr, channels, bit_depth, fmt = _decode_audio_to_mono_pcm(payload, "test.wav")
        self.assertEqual(sr, 16000)
        self.assertEqual(channels, 1)
        self.assertEqual(bit_depth, 16)
        self.assertEqual(fmt, "WAV")
        self.assertGreater(len(samples), 0)
        self.assertIsInstance(samples, np.ndarray)

    def test_decode_mp3_and_mp4_filename_formats(self) -> None:
        payload = self._make_wav_bytes(duration_seconds=1.0)
        _, _, _, _, fmt_mp3 = _decode_audio_to_mono_pcm(payload, "evidence_clip.mp3")
        _, _, _, _, fmt_mp4 = _decode_audio_to_mono_pcm(payload, "surveillance_recording.mp4")
        # Direct RIFF wav buffer will return WAV, test fallback format string with non-RIFF header logic
        samples_mp4, _, _, _, fmt_mp4_ext = _decode_audio_to_mono_pcm(payload, "test.mp4")
        self.assertIn(fmt_mp3, ["WAV", "MP3"])
        self.assertIn(fmt_mp4, ["WAV", "MP4"])
        self.assertGreater(len(samples_mp4), 0)

    def test_multi_speaker_diarization(self) -> None:
        sample_rate = 16000
        duration = 8.0
        total_frames = int(sample_rate * duration)
        frames = bytearray()
        # Alternate between low pitch (130 Hz - male) and high pitch (230 Hz - female)
        for i in range(total_frames):
            t = i / sample_rate
            if (0.0 <= t < 2.0) or (4.0 <= t < 6.0):
                freq = 130.0  # Male speaker
            else:
                freq = 230.0  # Female speaker
            val = int(0.4 * 32767 * math.sin(2 * math.pi * freq * t))
            frames.extend(struct.pack("<h", max(-32768, min(32767, val))))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)

        payload = buffer.getvalue()
        report = analyze_audio_bytes(payload, "dialogue.wav")
        spk_info = report.get("speaker_identification", {})
        self.assertGreaterEqual(spk_info.get("speakers_count", 0), 1)
        self.assertIn("timeline", spk_info)

    def test_authentic_signal_is_reported_as_no_tampering(self) -> None:
        payload = self._make_wav_bytes(amplitude=0.3, duration_seconds=3.0)
        report = analyze_audio_bytes(payload, "clean.wav")

        self.assertEqual(report["audio_status"], "Authentic")
        self.assertEqual(report["authenticity_status"], "No Significant Signs of Tampering")
        self.assertIn("enf_analysis", report)
        self.assertIn("examiner_statement", report)
        self.assertIn("contributing_indicators", report)
        self.assertGreaterEqual(report["confidence_score"], 80)

    def test_natural_speech_is_reported_as_authentic(self) -> None:
        sample_rate = 16000
        duration = 4.0
        total_frames = int(sample_rate * duration)
        frames = bytearray()
        for i in range(total_frames):
            t = i / sample_rate
            if (0.5 <= t <= 1.8) or (2.5 <= t <= 3.8):
                val = int(32767 * 0.25 * (math.sin(2 * math.pi * 220 * t) + 0.5 * math.sin(2 * math.pi * 440 * t)))
            else:
                val = int(32767 * 0.001 * (math.sin(2 * math.pi * 50 * t)))
            frames.extend(struct.pack("<h", max(-32768, min(32767, val))))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)

        report = analyze_audio_bytes(buffer.getvalue(), "speech.wav")
        self.assertEqual(report["audio_status"], "Authentic")
        self.assertEqual(report["authenticity_status"], "No Significant Signs of Tampering")

    def test_tampered_signal_with_silence_gap(self) -> None:
        payload = self._make_wav_bytes(amplitude=0.4, duration_seconds=3.0, insert_silence=True)
        report = analyze_audio_bytes(payload, "tampered_silence.wav")

        self.assertIn(report["audio_status"], ["Minor Anomalies", "Potentially Tampered"])
        self.assertIn(report["authenticity_status"], ["Minor Forensic Anomalies Detected", "Potential Audio Manipulation Detected"])
        self.assertIn("examiner_statement", report)

    def test_whisperx_word_level_speaker_merging(self) -> None:
        from app import _assign_speakers_to_words, _merge_words_into_speaker_blocks

        words = [
            {"word": "Good", "start": 0.0, "end": 0.5},
            {"word": "afternoon", "start": 0.5, "end": 1.2},
            {"word": "sir.", "start": 1.2, "end": 1.8},
            {"word": "Is", "start": 8.0, "end": 8.4},
            {"word": "there", "start": 8.4, "end": 8.8},
            {"word": "any", "start": 8.8, "end": 9.2},
            {"word": "problem?", "start": 9.2, "end": 10.0},
            {"word": "Yes", "start": 10.1, "end": 10.5},
            {"word": "sir.", "start": 10.5, "end": 11.0},
        ]

        diarization_intervals = [
            {"start": 0.0, "end": 7.9, "speaker": "Speaker 1"},
            {"start": 8.0, "end": 10.0, "speaker": "Speaker 2"},
            {"start": 10.1, "end": 15.0, "speaker": "Speaker 1"},
        ]

        words_assigned = _assign_speakers_to_words(words, diarization_intervals, total_duration=15.0)
        self.assertEqual(words_assigned[0]["speaker"], "Speaker 1")
        self.assertEqual(words_assigned[3]["speaker"], "Speaker 2")
        self.assertEqual(words_assigned[7]["speaker"], "Speaker 1")

        blocks = _merge_words_into_speaker_blocks(words_assigned)
        self.assertEqual(len(blocks), 3)

        self.assertEqual(blocks[0]["speaker"], "Speaker 1")
        self.assertEqual(blocks[0]["timestamp"], "00:00–00:02")
        self.assertEqual(blocks[0]["text"], "Good afternoon sir.")

        self.assertEqual(blocks[1]["speaker"], "Speaker 2")
        self.assertEqual(blocks[1]["timestamp"], "00:08–00:10")
        self.assertEqual(blocks[1]["text"], "Is there any problem?")

        self.assertEqual(blocks[2]["speaker"], "Speaker 1")
        self.assertEqual(blocks[2]["timestamp"], "00:10–00:11")
        self.assertEqual(blocks[2]["text"], "Yes sir.")


if __name__ == "__main__":
    unittest.main()

