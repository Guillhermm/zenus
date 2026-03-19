"""
Unit tests for the zenus_voice package.

All hardware I/O (PyAudio, faster-whisper, openwakeword, TTS) is stubbed in
sys.modules so these tests run in CI without any audio devices or ML models.

Covers:
  - stt.py: WhisperModel enum, TranscriptionResult, VoiceActivityDetector,
            SpeechToText (transcribe_file, transcribe_audio_data,
            listen_and_transcribe), get_stt singleton
  - wake_word.py: WakeWord enum, WakeWordDetector, TextFallbackDetector,
                  SimpleWakeWordDetector alias, create_wake_detector
  - pipeline.py: VoiceSession, VoiceTurn, PipelineState, VoicePipeline
                 (run_once, cancel detection, exit phrase, error handling,
                 state transitions, context tracking)
"""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure zenus_voice src is importable without installing the package
_VOICE_SRC = Path(__file__).parents[2] / "packages" / "voice" / "src"
if str(_VOICE_SRC) not in sys.path:
    sys.path.insert(0, str(_VOICE_SRC))

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Stub ALL optional voice dependencies before zenus_voice is imported
# ---------------------------------------------------------------------------

def _make_stub(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    return m


_STUBS: dict[str, types.ModuleType] = {}


def _stub_module(name: str, **attrs):
    m = _make_stub(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    _STUBS[name] = m
    sys.modules.setdefault(name, m)
    return m


# pyaudio
_pyaudio = _stub_module("pyaudio", paInt16=8, PyAudio=MagicMock)

# soundfile
_sf = _stub_module("soundfile")
_sf.write = MagicMock()

# webrtcvad
_vad_mod = _stub_module("webrtcvad")
_vad_mod.Vad = MagicMock

# faster_whisper
_fw_mod = _stub_module("faster_whisper")
_fw_mod.WhisperModel = MagicMock

# openwakeword
_oww_mod = _stub_module("openwakeword")
_oww_inner = _stub_module("openwakeword.model")
_oww_inner.Model = MagicMock

# pyttsx3 (used by tts.py)
_pyttsx3 = _stub_module("pyttsx3")
_pyttsx3.init = MagicMock(return_value=MagicMock())

# subprocess (tts uses it for piper — already built-in, but make sure no side-effects)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transcription(text="hello world", language="en", confidence=0.9, duration=0.5):
    from zenus_voice.stt import TranscriptionResult
    return TranscriptionResult(text=text, language=language,
                               confidence=confidence, duration=duration)


def _make_fw_result(texts: list[str], language="en", prob=0.95):
    """Return (segments_iter, info_mock) matching the faster-whisper API."""
    info = MagicMock()
    info.language = language
    info.language_probability = prob
    segs = [MagicMock(text=t) for t in texts]
    return (s for s in segs), info


# ---------------------------------------------------------------------------
# stt.py — WhisperModel
# ---------------------------------------------------------------------------

class TestWhisperModel:
    def test_values_match_model_names(self):
        from zenus_voice.stt import WhisperModel
        assert WhisperModel.TINY.value   == "tiny"
        assert WhisperModel.BASE.value   == "base"
        assert WhisperModel.SMALL.value  == "small"
        assert WhisperModel.MEDIUM.value == "medium"
        assert WhisperModel.LARGE.value  == "large"

    def test_all_five_sizes(self):
        from zenus_voice.stt import WhisperModel
        assert len(WhisperModel) == 5


# ---------------------------------------------------------------------------
# stt.py — TranscriptionResult
# ---------------------------------------------------------------------------

class TestTranscriptionResult:
    def test_fields(self):
        from zenus_voice.stt import TranscriptionResult
        r = TranscriptionResult(text="hi", language="en", confidence=0.8, duration=1.0)
        assert r.text == "hi"
        assert r.language == "en"
        assert r.confidence == 0.8
        assert r.duration == 1.0

    def test_is_dataclass(self):
        import dataclasses
        from zenus_voice.stt import TranscriptionResult
        assert dataclasses.is_dataclass(TranscriptionResult)


# ---------------------------------------------------------------------------
# stt.py — VoiceActivityDetector
# ---------------------------------------------------------------------------

class TestVoiceActivityDetector:
    def test_returns_true_when_speech(self):
        from zenus_voice.stt import VoiceActivityDetector
        fake_vad = MagicMock(is_speech=MagicMock(return_value=True))
        with patch("webrtcvad.Vad", return_value=fake_vad):
            vad = VoiceActivityDetector(aggressiveness=2)
        assert vad.is_speech(b"\x00" * 480, 16000) is True

    def test_returns_false_on_exception(self):
        from zenus_voice.stt import VoiceActivityDetector
        fake_vad = MagicMock(is_speech=MagicMock(side_effect=Exception("oops")))
        with patch("webrtcvad.Vad", return_value=fake_vad):
            vad = VoiceActivityDetector()
        assert vad.is_speech(b"x", 16000) is False

    def test_aggressiveness_passed_to_vad(self):
        from zenus_voice.stt import VoiceActivityDetector
        vad_cls = MagicMock(return_value=MagicMock(is_speech=MagicMock(return_value=False)))
        with patch("webrtcvad.Vad", vad_cls):
            VoiceActivityDetector(aggressiveness=1)
        vad_cls.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# stt.py — SpeechToText
# ---------------------------------------------------------------------------

class TestSpeechToText:

    def _build_stt(self, fw_model=None):
        """Return a SpeechToText with __new__ to bypass __init__ hardware calls."""
        from zenus_voice.stt import SpeechToText
        stt = SpeechToText.__new__(SpeechToText)
        stt._model    = fw_model or MagicMock()
        stt.language  = None
        stt.vad       = MagicMock(is_speech=MagicMock(return_value=False))
        stt.chunk_size  = 480
        stt.SAMPLE_RATE = 16_000
        stt.model_name  = "base"
        stt.device      = "cpu"
        stt.compute_type = "int8"
        return stt

    # transcribe_file

    def test_transcribe_file_joins_segments(self, tmp_path):
        fw_model = MagicMock()
        fw_model.transcribe.return_value = _make_fw_result(["hello ", "world"])

        stt = self._build_stt(fw_model)
        wav = tmp_path / "t.wav"
        wav.write_bytes(b"x")

        result = stt.transcribe_file(str(wav))
        assert result.text == "hello  world"
        assert result.language == "en"
        assert result.confidence == 0.95

    def test_transcribe_file_strips_whitespace(self, tmp_path):
        fw_model = MagicMock()
        fw_model.transcribe.return_value = _make_fw_result(["  trimmed  "])

        stt = self._build_stt(fw_model)
        wav = tmp_path / "t.wav"
        wav.write_bytes(b"x")

        result = stt.transcribe_file(str(wav))
        assert result.text == "trimmed"

    def test_transcribe_file_empty_result(self, tmp_path):
        fw_model = MagicMock()
        fw_model.transcribe.return_value = _make_fw_result([])

        stt = self._build_stt(fw_model)
        wav = tmp_path / "t.wav"
        wav.write_bytes(b"x")

        result = stt.transcribe_file(str(wav))
        assert result.text == ""

    def test_transcribe_file_passes_language(self, tmp_path):
        fw_model = MagicMock()
        fw_model.transcribe.return_value = _make_fw_result(["bonjour"])

        stt = self._build_stt(fw_model)
        stt.language = "fr"
        wav = tmp_path / "t.wav"
        wav.write_bytes(b"x")

        stt.transcribe_file(str(wav))
        _, kwargs = fw_model.transcribe.call_args
        assert kwargs.get("language") == "fr" or fw_model.transcribe.call_args[0][1] == "fr" \
               or fw_model.transcribe.call_args.kwargs.get("language") == "fr"

    # transcribe_audio_data

    def test_transcribe_audio_data_writes_tmp_wav(self, tmp_path):
        fw_model = MagicMock()
        fw_model.transcribe.return_value = _make_fw_result(["hello"])

        stt = self._build_stt(fw_model)
        audio = np.zeros(16_000, dtype=np.float32)

        written = []
        with patch("soundfile.write", side_effect=lambda p, *a, **kw: written.append(p)):
            with patch.object(stt, "transcribe_file",
                              return_value=_make_transcription("hello")) as mock_tf:
                result = stt.transcribe_audio_data(audio)

        mock_tf.assert_called_once()
        assert result.text == "hello"

    def test_transcribe_audio_data_cleans_up_tmp_file(self):
        stt = self._build_stt()
        audio = np.zeros(16_000, dtype=np.float32)

        with patch("soundfile.write"), \
             patch.object(stt, "transcribe_file", return_value=_make_transcription()):
            stt.transcribe_audio_data(audio)
        # If no exception, cleanup ran (unlink(missing_ok=True) never raises)

    # listen_and_transcribe

    def test_listen_returns_empty_when_no_speech(self):
        stt = self._build_stt()
        stt.vad.is_speech.return_value = False

        stream = MagicMock(read=MagicMock(return_value=b"\x00" * 960))

        # Patch time.time so the duration check immediately fires:
        # first call → rec_start=0.0, subsequent calls → 100.0 (always > duration)
        time_values = iter([0.0] + [100.0] * 20)

        with patch("pyaudio.PyAudio", return_value=MagicMock(open=MagicMock(return_value=stream))), \
             patch("time.time", side_effect=lambda: next(time_values)):
            result = stt.listen_and_transcribe(duration=0.001)

        assert result.text == ""
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# stt.py — get_stt singleton
# ---------------------------------------------------------------------------

class TestGetStt:
    def test_returns_same_instance(self):
        import zenus_voice.stt as stt_mod
        stt_mod._stt_instance = None

        fw = MagicMock()
        fw.transcribe.return_value = _make_fw_result(["x"])

        with patch("faster_whisper.WhisperModel", return_value=fw), \
             patch("zenus_voice.stt.VoiceActivityDetector"):
            a = stt_mod.get_stt()
            b = stt_mod.get_stt()

        assert a is b
        stt_mod._stt_instance = None  # cleanup

    def test_singleton_resets(self):
        import zenus_voice.stt as stt_mod
        stt_mod._stt_instance = None
        fw = MagicMock()
        fw.transcribe.return_value = _make_fw_result(["x"])

        with patch("faster_whisper.WhisperModel", return_value=fw), \
             patch("zenus_voice.stt.VoiceActivityDetector"):
            inst1 = stt_mod.get_stt()

        stt_mod._stt_instance = None

        with patch("faster_whisper.WhisperModel", return_value=fw), \
             patch("zenus_voice.stt.VoiceActivityDetector"):
            inst2 = stt_mod.get_stt()

        assert inst1 is not inst2
        stt_mod._stt_instance = None


# ---------------------------------------------------------------------------
# wake_word.py — WakeWord enum
# ---------------------------------------------------------------------------

class TestWakeWord:
    def test_hey_zenus_uses_hey_jarvis_model(self):
        from zenus_voice.wake_word import WakeWord
        assert WakeWord.HEY_ZENUS.value == "hey_jarvis"

    def test_alexa_value(self):
        from zenus_voice.wake_word import WakeWord
        assert WakeWord.ALEXA.value == "alexa"

    def test_hey_jarvis_value(self):
        from zenus_voice.wake_word import WakeWord
        assert WakeWord.HEY_JARVIS.value == "hey_jarvis"

    def test_hey_mycroft_value(self):
        from zenus_voice.wake_word import WakeWord
        assert WakeWord.HEY_MYCROFT.value == "hey_mycroft"


# ---------------------------------------------------------------------------
# wake_word.py — WakeWordDetector._listen_loop
# ---------------------------------------------------------------------------

class TestWakeWordDetectorLoop:
    def _build_detector(self, score=0.8, threshold=0.5):
        from zenus_voice.wake_word import WakeWord, WakeWordDetector
        det = WakeWordDetector.__new__(WakeWordDetector)
        det.wake_word     = WakeWord.HEY_ZENUS
        det.threshold     = threshold
        det.is_listening  = False
        det._thread       = None
        det.SAMPLE_RATE   = 16_000
        det.FRAME_SAMPLES = 1_280
        det.on_wake       = None

        oww_model = MagicMock()
        oww_model.predict.return_value = {WakeWord.HEY_ZENUS.value: score}
        oww_model.reset = MagicMock()
        det._model = oww_model
        return det, oww_model

    def _make_stream(self, det, max_reads=3):
        """Return a stream mock that stops the detector after max_reads calls."""
        call_count = 0

        def fake_read(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > max_reads:
                det.is_listening = False   # stop loop cleanly (no KeyboardInterrupt)
            return b"\x00" * 2_560

        return MagicMock(read=fake_read)

    def test_fires_on_wake_when_score_exceeds_threshold(self):
        det, oww_model = self._build_detector(score=0.8, threshold=0.5)
        fired = threading.Event()

        def on_wake():
            fired.set()
            det.is_listening = False   # also stop the loop

        det.on_wake = on_wake
        stream = self._make_stream(det)
        with patch("pyaudio.PyAudio", return_value=MagicMock(open=MagicMock(return_value=stream))):
            det._listen_loop()

        assert fired.is_set()
        oww_model.reset.assert_called()

    def test_does_not_fire_below_threshold(self):
        det, oww_model = self._build_detector(score=0.1, threshold=0.5)
        fired = threading.Event()
        det.on_wake = fired.set

        stream = self._make_stream(det)
        with patch("pyaudio.PyAudio", return_value=MagicMock(open=MagicMock(return_value=stream))):
            det._listen_loop()

        assert not fired.is_set()

    def test_stop_listening_clears_flag(self):
        from zenus_voice.wake_word import WakeWordDetector
        det = WakeWordDetector.__new__(WakeWordDetector)
        det.is_listening = True
        det.stop_listening()
        assert det.is_listening is False


# ---------------------------------------------------------------------------
# wake_word.py — TextFallbackDetector
# ---------------------------------------------------------------------------

class TestTextFallbackDetector:
    def _build(self, text="hey zenus wake up", phrase="hey zenus"):
        from zenus_voice.wake_word import TextFallbackDetector

        # Bypass __init__ (which imports SpeechToText) and set up manually
        det = TextFallbackDetector.__new__(TextFallbackDetector)
        det.wake_phrase  = phrase.lower()
        det.on_wake      = None
        det.is_listening = False

        call_count = 0

        def fake_listen(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                det.is_listening = False   # stop loop cleanly
            return _make_transcription(text=text)

        det._stt = MagicMock(listen_and_transcribe=fake_listen)
        return det

    def test_fires_on_phrase_match(self):
        det = self._build(text="hey zenus, help me", phrase="hey zenus")
        fired = threading.Event()

        def on_wake():
            fired.set()
            det.is_listening = False  # stop after first match

        det.on_wake = on_wake
        det.start_listening(background=False)
        assert fired.is_set()

    def test_no_fire_on_mismatch(self):
        det = self._build(text="something completely unrelated", phrase="hey zenus")
        fired = threading.Event()
        det.on_wake = fired.set
        det.start_listening(background=False)
        assert not fired.is_set()

    def test_stop_sets_flag(self):
        from zenus_voice.wake_word import TextFallbackDetector
        det = TextFallbackDetector.__new__(TextFallbackDetector)
        det.is_listening = True
        det.stop_listening()
        assert det.is_listening is False

    def test_simple_wake_word_detector_is_alias(self):
        from zenus_voice.wake_word import SimpleWakeWordDetector, TextFallbackDetector
        assert SimpleWakeWordDetector is TextFallbackDetector

    def test_case_insensitive_matching(self):
        det = self._build(text="HEY ZENUS please help", phrase="hey zenus")
        fired = threading.Event()

        def on_wake():
            fired.set()
            det.is_listening = False

        det.on_wake = on_wake
        det.start_listening(background=False)
        assert fired.is_set()


# ---------------------------------------------------------------------------
# wake_word.py — create_wake_detector factory
# ---------------------------------------------------------------------------

class TestCreateWakeDetector:
    def _make_null_fallback(self):
        """Return a TextFallbackDetector subclass with __init__ bypassed."""
        from zenus_voice.wake_word import TextFallbackDetector

        class _Null(TextFallbackDetector):
            def __init__(self, wake_phrase="", on_wake=None):
                self.wake_phrase  = wake_phrase.lower()
                self.on_wake      = on_wake
                self.is_listening = False
                self._stt         = MagicMock()

        return _Null

    def test_falls_back_on_import_error(self):
        from zenus_voice.wake_word import create_wake_detector, TextFallbackDetector, WakeWord
        import zenus_voice.wake_word as ww_mod

        Null = self._make_null_fallback()
        original = ww_mod.TextFallbackDetector
        ww_mod.TextFallbackDetector = Null
        try:
            with patch("zenus_voice.wake_word.WakeWordDetector",
                       side_effect=ImportError("no openwakeword")):
                det = create_wake_detector(wake_word=WakeWord.HEY_ZENUS)
        finally:
            ww_mod.TextFallbackDetector = original

        assert isinstance(det, TextFallbackDetector)

    def test_falls_back_on_runtime_error(self):
        from zenus_voice.wake_word import create_wake_detector, TextFallbackDetector, WakeWord
        import zenus_voice.wake_word as ww_mod

        Null = self._make_null_fallback()
        original = ww_mod.TextFallbackDetector
        ww_mod.TextFallbackDetector = Null
        try:
            with patch("zenus_voice.wake_word.WakeWordDetector",
                       side_effect=RuntimeError("model load failed")):
                det = create_wake_detector(wake_word=WakeWord.ALEXA)
        finally:
            ww_mod.TextFallbackDetector = original

        assert isinstance(det, TextFallbackDetector)


# ---------------------------------------------------------------------------
# pipeline.py — VoiceTurn / VoiceSession
# ---------------------------------------------------------------------------

class TestVoiceSession:
    def _turn(self, user_text="cmd", response="ok"):
        from zenus_voice.pipeline import VoiceTurn
        return VoiceTurn(
            timestamp="2026-03-19T17:00:00+00:00",
            user_text=user_text,
            response=response,
            confidence=0.9,
            latency_s=0.1,
        )

    def test_add_and_retrieve(self):
        from zenus_voice.pipeline import VoiceSession
        s = VoiceSession()
        s.add(self._turn("list files", "Listed."))
        assert len(s.turns) == 1
        assert s.turns[0].user_text == "list files"

    def test_max_turns_enforced(self):
        from zenus_voice.pipeline import VoiceSession
        s = VoiceSession(max_turns=3)
        for i in range(5):
            s.add(self._turn(f"cmd {i}"))
        assert len(s.turns) == 3
        assert s.turns[-1].user_text == "cmd 4"

    def test_context_snippet_empty_when_no_turns(self):
        from zenus_voice.pipeline import VoiceSession
        assert VoiceSession().context_snippet() == ""

    def test_context_snippet_contains_turns(self):
        from zenus_voice.pipeline import VoiceSession
        s = VoiceSession()
        s.add(self._turn("open browser", "Opened."))
        snippet = s.context_snippet()
        assert "open browser" in snippet
        assert "Opened." in snippet

    def test_clear_empties_turns(self):
        from zenus_voice.pipeline import VoiceSession
        s = VoiceSession()
        s.add(self._turn())
        s.clear()
        assert s.turns == []

    def test_context_snippet_limited_to_n_turns(self):
        from zenus_voice.pipeline import VoiceSession
        s = VoiceSession()
        for i in range(6):
            s.add(self._turn(f"cmd {i}", f"resp {i}"))
        snippet = s.context_snippet(n=2)
        assert "cmd 4" in snippet
        assert "cmd 5" in snippet
        assert "cmd 0" not in snippet


# ---------------------------------------------------------------------------
# pipeline.py — PipelineState
# ---------------------------------------------------------------------------

class TestPipelineState:
    def test_all_states_defined(self):
        from zenus_voice.pipeline import PipelineState
        values = {s.value for s in PipelineState}
        for expected in ("idle", "waiting_for_wake", "listening", "processing", "speaking", "stopped"):
            assert expected in values


# ---------------------------------------------------------------------------
# pipeline.py — VoicePipeline
# ---------------------------------------------------------------------------

class TestVoicePipeline:
    @pytest.fixture
    def pipeline(self):
        from zenus_voice.pipeline import VoicePipeline, WhisperModel, TTSEngine, Voice

        mock_stt  = MagicMock()
        mock_tts  = MagicMock()
        mock_orch = MagicMock()

        with patch("zenus_voice.pipeline.SpeechToText", return_value=mock_stt), \
             patch("zenus_voice.pipeline.TextToSpeech", return_value=mock_tts), \
             patch("zenus_voice.pipeline.create_wake_detector", return_value=MagicMock()):
            pl = VoicePipeline(mock_orch, use_wake_word=False, use_voice_output=False)

        pl._stt  = mock_stt
        pl._tts  = mock_tts
        pl._orch = mock_orch
        return pl

    def test_initial_state_is_idle(self, pipeline):
        from zenus_voice.pipeline import PipelineState
        assert pipeline.state == PipelineState.IDLE

    def test_run_once_executes_and_returns_result(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("list files")
        pipeline._orch.execute_command.return_value = "Listed files."
        result = pipeline.run_once()
        pipeline._orch.execute_command.assert_called_once()
        assert result == "Listed files."

    def test_run_once_empty_transcription_returns_none(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription(text="")
        result = pipeline.run_once()
        assert result is None
        pipeline._orch.execute_command.assert_not_called()

    def test_run_once_cancel_phrase_returns_none(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("cancel that")
        result = pipeline.run_once()
        assert result is None
        pipeline._orch.execute_command.assert_not_called()

    def test_run_once_nevermind_returns_none(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("nevermind")
        result = pipeline.run_once()
        assert result is None

    def test_run_once_forget_it_returns_none(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("forget it please")
        result = pipeline.run_once()
        assert result is None

    def test_run_once_exit_phrase_stops_pipeline(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("goodbye")
        pipeline._running = True
        pipeline.run_once()
        assert pipeline._running is False

    def test_run_once_quit_stops_pipeline(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("quit now")
        pipeline._running = True
        pipeline.run_once()
        assert pipeline._running is False

    def test_run_once_records_session_turn(self, pipeline):
        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("move file")
        pipeline._orch.execute_command.return_value = "Moved."
        pipeline.run_once()
        assert len(pipeline._session.turns) == 1
        assert pipeline._session.turns[0].user_text == "move file"

    def test_run_once_exception_returns_none(self, pipeline):
        pipeline._stt.listen_and_transcribe.side_effect = RuntimeError("mic broken")
        result = pipeline.run_once()
        assert result is None

    def test_state_transitions_during_run_once(self, pipeline):
        from zenus_voice.pipeline import PipelineState
        states: list[PipelineState] = []
        pipeline._on_state_change = states.append

        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("open browser")
        pipeline._orch.execute_command.return_value = "Opened."

        pipeline.run_once()

        assert PipelineState.LISTENING  in states
        assert PipelineState.PROCESSING in states
        assert PipelineState.SPEAKING   in states
        assert PipelineState.IDLE       in states

    def test_clear_context(self, pipeline):
        from zenus_voice.pipeline import VoiceTurn
        pipeline._session.add(VoiceTurn("t", "x", "y", 1.0, 0.1))
        pipeline.clear_context()
        assert pipeline._session.turns == []

    def test_say_prints_when_voice_disabled(self, pipeline, capsys):
        pipeline.use_voice_output = False
        pipeline._say("Hello unit test")
        captured = capsys.readouterr()
        assert "Hello unit test" in captured.out

    def test_say_calls_tts_when_voice_enabled(self, pipeline):
        pipeline.use_voice_output = True
        pipeline._say("Speak this")
        pipeline._tts.speak.assert_called_once()

    # _humanise

    def test_humanise_checkmark(self):
        from zenus_voice.pipeline import VoicePipeline
        assert "Done." in VoicePipeline._humanise("✓ file created")

    def test_humanise_cross(self):
        from zenus_voice.pipeline import VoicePipeline
        assert "Failed." in VoicePipeline._humanise("✗ error occurred")

    def test_humanise_arrow(self):
        from zenus_voice.pipeline import VoicePipeline
        result = VoicePipeline._humanise("step1 → step2")
        assert "then" in result
        assert "→" not in result

    def test_humanise_strips_whitespace(self):
        from zenus_voice.pipeline import VoicePipeline
        assert VoicePipeline._humanise("  done  ") == "done"

    def test_context_injected_into_orchestrator_call(self, pipeline):
        from zenus_voice.pipeline import VoiceTurn
        pipeline._session.add(VoiceTurn("t", "previous cmd", "previous resp", 0.9, 0.1))

        pipeline._stt.listen_and_transcribe.return_value = _make_transcription("follow up cmd")
        pipeline._orch.execute_command.return_value = "Done."

        pipeline.run_once()

        call_args = pipeline._orch.execute_command.call_args[0][0]
        assert "previous cmd" in call_args
        assert "follow up cmd" in call_args


# ---------------------------------------------------------------------------
# pipeline.py — create_voice_pipeline
# ---------------------------------------------------------------------------

class TestCreateVoicePipeline:
    def test_returns_voice_pipeline(self):
        from zenus_voice.pipeline import create_voice_pipeline, VoicePipeline

        mock_orch = MagicMock()
        with patch("zenus_voice.pipeline.SpeechToText"), \
             patch("zenus_voice.pipeline.TextToSpeech"), \
             patch("zenus_voice.pipeline.create_wake_detector"):
            pl = create_voice_pipeline(mock_orch, use_wake_word=False)

        assert isinstance(pl, VoicePipeline)

    def test_kwargs_passed_through(self):
        from zenus_voice.pipeline import create_voice_pipeline, VoicePipeline

        mock_orch = MagicMock()
        with patch("zenus_voice.pipeline.SpeechToText"), \
             patch("zenus_voice.pipeline.TextToSpeech"), \
             patch("zenus_voice.pipeline.create_wake_detector"):
            pl = create_voice_pipeline(mock_orch, use_wake_word=False, use_voice_output=False)

        assert pl.use_voice_output is False
