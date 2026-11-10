# MIT License

"""Pluggable online translation backends for CATS.

CATS translates in two phases: the internal dictionary is applied first (see
``tools/translate.py``), and only the Japanese text the dictionary could not
resolve is sent to an *online* provider to fill the gaps. This module holds
those providers.

The user picks which provider fills the gaps (Google, DeepL, LibreTranslate,
MyMemory) or ``internal`` for dictionary-only. All network work happens inside
the single batched pass in ``update_dictionary`` so it never fires one request
per name, and every provider fails soft: on any error the original text is
returned unchanged so the operator degrades to dictionary-only instead of
hanging or crashing Blender's UI thread.
"""

import json
import concurrent.futures

# ``requests`` ships with Blender's Python but is not guaranteed in a stripped
# build. Guard the import so a missing module disables online translation
# instead of stopping the add-on from registering (see test_requests_optional).
try:
    import requests
except ImportError:
    requests = None


# Service ids stored in settings / shown in the UI enum.
SERVICE_INTERNAL = "internal"
SERVICE_GOOGLE = "google"
SERVICE_DEEPL = "deepl"
SERVICE_LIBRE = "libretranslate"
SERVICE_MYMEMORY = "mymemory"


def online_access_allowed():
    """Whether Preferences > System > Allow Online Access is on."""
    try:
        import bpy
    except ImportError:
        return True
    return bpy.app.online_access


class TranslationError(Exception):
    """Raised by a provider when a single translation attempt fails."""
    pass


def safe_decode_text(text):
    """Best-effort repair of text that arrived in a non-UTF-8 Japanese encoding.

    Model authoring tools sometimes hand us names mangled through cp932/shift-jis.
    We try a few common encodings and fall back to the original string.
    """
    if not text or not isinstance(text, str):
        return text
    try:
        text.encode("utf-8")
        return text
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    for encoding in ("shift-jis", "cp932", "euc-jp", "iso-2022-jp"):
        try:
            return text.encode("latin-1", errors="ignore").decode(encoding, errors="ignore")
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return text


def _concurrent_batch(texts, worker, max_workers, timeout):
    """Run ``worker(text)`` over ``texts`` with a bounded thread pool.

    Preserves input order and never raises: a failed or timed-out item keeps its
    original text. This replaces per-item thread spawning with a small fixed pool
    so a large model can't flood the network or stall the UI.
    """
    results = [None] * len(texts)
    max_workers = max(1, min(max_workers, len(texts)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(worker, text): i for i, text in enumerate(texts)
        }
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result(timeout=timeout)
            except Exception as e:
                print(f"CATS translate: item failed ({e}); keeping original")
                results[index] = texts[index]
    for i, value in enumerate(results):
        if value is None:
            results[i] = texts[i]
    return results


class TranslationProvider:
    """Base provider. Subclasses implement :meth:`translate_text`."""

    name = "Base"
    requires_requests = True
    max_workers = 1
    request_timeout = 15

    def is_available(self):
        """Whether this provider can be used right now (module + config present)."""
        if self.requires_requests and (requests is None or not online_access_allowed()):
            return False
        return True

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        raise NotImplementedError

    def translate_batch(self, texts, source_lang="ja", target_lang="en"):
        """Translate a list of strings, preserving order and failing soft."""
        if not texts:
            return []

        def worker(text):
            if not text or not text.strip():
                return text
            return self.translate_text(safe_decode_text(text), source_lang, target_lang)

        return _concurrent_batch(texts, worker, self.max_workers, self.request_timeout)


class NullProvider(TranslationProvider):
    """Internal-dictionary-only: performs no online translation."""

    name = "Internal dictionary"
    requires_requests = False

    def is_available(self):
        return True

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        return text

    def translate_batch(self, texts, source_lang="ja", target_lang="en"):
        return list(texts)


class GoogleProvider(TranslationProvider):
    """Free Google endpoint, tokenless ``translate_a/single`` (client=gtx).

    Kept at low concurrency because the free endpoint rate-limits/bans aggressively.
    """

    name = "Google Translate"
    max_workers = 2
    request_timeout = 10
    _endpoint = "https://translate.googleapis.com/translate_a/single"

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        params = {
            "client": "gtx",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text,
        }
        try:
            response = requests.get(self._endpoint, params=params, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            raise TranslationError(f"Google request failed: {e}")

        # Response shape: [[[translated, original, ...], ...], ...]
        if not data or not data[0]:
            raise TranslationError("Google returned no translation")
        return "".join(segment[0] for segment in data[0] if segment and segment[0])

    def is_available(self):
        if not super().is_available():
            return False
        try:
            self.translate_text("猫")
            return True
        except TranslationError:
            return False


class DeepLProvider(TranslationProvider):
    """DeepL API (free or pro). Requires an API key; supports native batching."""

    name = "DeepL"
    request_timeout = 30
    _batch_size = 50
    _lang_map = {
        "ja": "JA", "en": "EN", "ko": "KO", "zh": "ZH", "es": "ES", "fr": "FR",
        "de": "DE", "it": "IT", "pt": "PT", "ru": "RU", "nl": "NL", "pl": "PL",
    }

    def __init__(self, api_key="", use_free_api=True):
        self.api_key = api_key
        self.use_free_api = use_free_api
        self._base_url = "https://api-free.deepl.com" if use_free_api else "https://api.deepl.com"

    def is_available(self):
        return super().is_available() and bool(self.api_key)

    def _headers(self):
        return {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        return self.translate_batch([text], source_lang, target_lang)[0]

    def translate_batch(self, texts, source_lang="ja", target_lang="en"):
        if not texts:
            return []
        if not self.api_key:
            print("CATS translate: DeepL API key missing; keeping originals")
            return list(texts)

        source = self._lang_map.get(source_lang, source_lang.upper())
        target = self._lang_map.get(target_lang, target_lang.upper())
        endpoint = f"{self._base_url}/v2/translate"

        results = list(texts)
        # Only send non-empty strings; remember where each one came from.
        indices = [i for i, t in enumerate(texts) if t and t.strip()]

        for start in range(0, len(indices), self._batch_size):
            chunk = indices[start:start + self._batch_size]
            form = [("source_lang", source), ("target_lang", target)]
            for i in chunk:
                form.append(("text", safe_decode_text(texts[i])))
            try:
                response = requests.post(
                    endpoint, headers=self._headers(), data=form, timeout=self.request_timeout
                )
                response.raise_for_status()
                translations = response.json().get("translations", [])
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                print(f"CATS translate: DeepL batch failed ({e}); keeping originals")
                continue

            if len(translations) == len(chunk):
                for i, translation in zip(chunk, translations):
                    results[i] = translation.get("text", texts[i])
            else:
                print("CATS translate: DeepL returned unexpected count; keeping originals")

        return results


class LibreTranslateProvider(TranslationProvider):
    """LibreTranslate, self-hosted or the public server. Optional API key."""

    name = "LibreTranslate"
    max_workers = 3
    request_timeout = 15

    def __init__(self, api_url="https://libretranslate.com", api_key=""):
        self.api_url = (api_url or "https://libretranslate.com").rstrip("/") + "/"
        self.api_key = api_key

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        payload = {"q": text, "source": source_lang, "target": target_lang, "format": "text"}
        if self.api_key:
            payload["api_key"] = self.api_key
        try:
            response = requests.post(
                f"{self.api_url}translate", json=payload, timeout=self.request_timeout
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            raise TranslationError(f"LibreTranslate request failed: {e}")

        if "translatedText" not in data:
            raise TranslationError("LibreTranslate returned no translation")
        return data["translatedText"]


class MyMemoryProvider(TranslationProvider):
    """MyMemory free API. No key required; an email raises the daily quota."""

    name = "MyMemory"
    max_workers = 2
    request_timeout = 15
    _endpoint = "https://api.mymemory.translated.net/get"

    def __init__(self, email=""):
        self.email = email

    def translate_text(self, text, source_lang="ja", target_lang="en"):
        params = {"q": text, "langpair": f"{source_lang}|{target_lang}"}
        if self.email:
            params["de"] = self.email
        try:
            response = requests.get(self._endpoint, params=params, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            raise TranslationError(f"MyMemory request failed: {e}")

        if data.get("responseStatus") != 200:
            raise TranslationError(data.get("responseDetails", "MyMemory error"))
        return data["responseData"]["translatedText"]


def get_active_provider():
    """Build the provider the user selected, reading credentials from settings.

    Falls back to :class:`NullProvider` (internal-only) for an unknown service or
    when ``requests`` is unavailable, so translation never hard-fails.
    """
    # Imported lazily to avoid a circular import (settings -> translate -> here).
    from . import settings as Settings

    service = Settings.get_translation_service() or SERVICE_GOOGLE

    if service == SERVICE_INTERNAL or requests is None:
        return NullProvider()
    if service == SERVICE_GOOGLE:
        return GoogleProvider()
    if service == SERVICE_DEEPL:
        return DeepLProvider(
            api_key=Settings.get_deepl_api_key(),
            use_free_api=True,
        )
    if service == SERVICE_LIBRE:
        return LibreTranslateProvider(
            api_url=Settings.get_libretranslate_url(),
            api_key=Settings.get_libretranslate_api_key(),
        )
    if service == SERVICE_MYMEMORY:
        return MyMemoryProvider(email=Settings.get_mymemory_email())
    return NullProvider()
