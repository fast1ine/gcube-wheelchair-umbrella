import queue
import threading


class TtsSpeaker:
    ALLOWED_MESSAGES = frozenset(("우산을 펼칩니다", "우산을 접습니다"))

    def __init__(self, on_error=None):
        self._messages = queue.Queue()
        self._on_error = on_error or (lambda _message: None)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def speak(self, text):
        message = str(text).strip()
        if message not in self.ALLOWED_MESSAGES:
            raise ValueError("TTS only supports umbrella open/close announcements.")
        self._messages.put(message)

    def close(self):
        self._messages.put(None)

    def _run(self):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            for voice in engine.getProperty("voices"):
                description = "{} {} {}".format(
                    getattr(voice, "id", ""),
                    getattr(voice, "name", ""),
                    getattr(voice, "languages", ""),
                ).lower()
                if "korean" in description or "ko-kr" in description or "heami" in description:
                    engine.setProperty("voice", voice.id)
                    break
        except Exception as error:
            self._on_error("TTS 초기화 실패: {}".format(error))
            return
        while True:
            message = self._messages.get()
            if message is None:
                break
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception as error:
                self._on_error("TTS 재생 실패: {}".format(error))
        try:
            engine.stop()
        except Exception:
            pass
