# -*- coding: utf-8 -*-
"""
CC Subs Pro - AI Audio Transcriber
Maneja la transcripción de fragmentos breves de audio correspondientes a huecos
en la línea de tiempo usando OpenRouter (Whisper y Gemini Multimodal).
"""

import os
import json
import base64
import urllib.request
import urllib.error
import logging
from typing import Optional

from core.text_utils import clean_subtitle_text

logger = logging.getLogger('CCSubsPro.Transcriber')

OPENROUTER_TRANSCRIPTION_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT_TRANSCRIBE = (
    "Eres un transcriptor de audio profesional en español. "
    "Tu única tarea es transcribir exactamente las palabras habladas en el audio. "
    "Reglas estrictas:\n"
    "1. NO incluyas introducciones, comentarios ni explicaciones.\n"
    "2. NO coloques comas (,), puntos (.) ni dos puntos (:).\n"
    "3. Si solo hay silencio, ruido o música de fondo sin voz inteligible, responde exactamente: VACIO\n"
    "Devuelve únicamente las palabras transcritas."
)

class AudioTranscriber:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_key_from_config() or os.environ.get('OPENROUTER_API_KEY') or ""

    def _load_key_from_config(self) -> str:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_path = os.path.join(script_dir, '.cc_subs_pro_config.json')
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    return d.get('openrouter_key') or d.get('api_key') or ""
            except Exception:
                pass
        return ""

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribe un archivo de audio WAV o MP3 y devuelve el texto limpio (sin comas ni puntos).
        """
        if not os.path.isfile(audio_file_path):
            logger.warning(f"Audio file not found: {audio_file_path}")
            return ""

        if not self.is_configured():
            logger.info("OpenRouter API key is not configured for audio transcription.")
            return ""

        try:
            with open(audio_file_path, 'rb') as f:
                audio_bytes = f.read()
            b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading audio file for transcription: {e}")
            return ""

        ext = os.path.splitext(audio_file_path)[1].lower().replace('.', '')
        fmt = "wav" if ext == "wav" else "mp3"

        # 1. Intentar endpoint dedicado de transcripción Whisper
        whisper_result = self._try_whisper_endpoint(b64_audio, fmt)
        if whisper_result is not None:
            return clean_subtitle_text(whisper_result)

        # 2. Intentar endpoint chat completions con Gemini multimodal
        gemini_result = self._try_gemini_multimodal(b64_audio, fmt)
        if gemini_result is not None:
            return clean_subtitle_text(gemini_result)

        return ""

    def _try_whisper_endpoint(self, b64_audio: str, fmt: str) -> Optional[str]:
        for model in ["openai/whisper-large-v3", "openai/whisper-1"]:
            payload = {
                "model": model,
                "input_audio": {
                    "data": b64_audio,
                    "format": fmt
                }
            }
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                OPENROUTER_TRANSCRIPTION_URL,
                data=req_data,
                headers={
                    "Authorization": f"Bearer {self.api_key.strip()}",
                    "Content-Type": "application/json"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    text = data.get('text', '').strip()
                    if text and text.upper() != 'VACIO':
                        return text
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='ignore')
                logger.debug(f"Whisper endpoint error ({model}, {e.code}): {err_body[:120]}")
                if e.code == 402:
                    # Balance insufficient on audio endpoint, try chat endpoint
                    break
            except Exception as e:
                logger.debug(f"Whisper exception ({model}): {e}")
        return None

    def _try_gemini_multimodal(self, b64_audio: str, fmt: str) -> Optional[str]:
        for model in ["google/gemini-2.5-flash", "google/gemini-2.0-flash-001"]:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": SYSTEM_PROMPT_TRANSCRIBE},
                            {"type": "input_audio", "input_audio": {"data": b64_audio, "format": fmt}}
                        ]
                    }
                ],
                "temperature": 0.1
            }
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                OPENROUTER_CHAT_URL,
                data=req_data,
                headers={
                    "Authorization": f"Bearer {self.api_key.strip()}",
                    "Content-Type": "application/json"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '').strip()
                        if content and content.upper() != 'VACIO':
                            return content
            except Exception as e:
                logger.debug(f"Gemini multimodal exception ({model}): {e}")
        return None
