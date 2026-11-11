import contextlib
import os
import time

from live_caption_recorder.core.recorder import Recorder, Status


class FakeSource:
    """Plays back a scripted list of caption snapshots."""

    def __init__(self, frames, available=True):
        self.frames = list(frames)
        self.available = available
        self.hidden = self.restored = False
        self.i = 0

    def thread_context(self):
        return contextlib.nullcontext()

    def ensure_running(self):
        return self.available

    def hide(self):
        self.hidden = True

    def keep_hidden(self):
        pass

    def is_hung(self):
        return False

    def read(self):
        frame = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return frame

    def restore(self):
        self.restored = True


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def fast(rec):
    rec.POLL_SECONDS = 0.01
    rec.AUTOSAVE_SECONDS = 0.0
    return rec


def test_records_and_autosaves(tmp_path):
    src = FakeSource(["Old text.", "Old text. New sentence here. More words. And",
                      "Old text. New sentence here. More words. And more."])
    rec = fast(Recorder(src, autosave_dir=str(tmp_path)))
    rec.start()
    assert wait_for(lambda: rec.transcript.texts == ["New sentence here."])
    assert src.hidden and rec.status == Status.LISTENING
    assert wait_for(lambda: src.i > len(src.frames) + 1)   # every frame consumed
    rec.stop()
    assert rec.transcript.texts == ["New sentence here.", "More words.", "And more."]
    assert rec.status == Status.PAUSED
    files = os.listdir(tmp_path)
    assert len(files) == 1 and "More words." in (tmp_path / files[0]).read_text(encoding="utf-8")
    rec.shutdown()
    assert src.restored


def test_unavailable_source_sets_status():
    rec = fast(Recorder(FakeSource([""], available=False)))
    rec.start()
    assert wait_for(lambda: rec.status == Status.UNAVAILABLE)
    assert not rec.running


def test_clear_resets_elapsed_and_transcript():
    rec = fast(Recorder(FakeSource(["", "", "A b c. D e. F"])))
    rec.start()
    assert wait_for(lambda: rec.transcript.texts == ["A b c."])
    rec.clear()
    assert rec.transcript.texts == []
    rec.shutdown()
