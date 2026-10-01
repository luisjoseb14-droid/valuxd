import os
import json
import re
import urllib.request
import urllib.error
import logging
from typing import List, Dict, Any, Optional
from core.text_utils import clean_subtitle_text, sanitize_highlight_phrase, INVALID_TRAILING_HIGHLIGHT_WORDS, INVALID_LEADING_HIGHLIGHT_WORDS, SPANISH_STOPWORDS
from ai.openrouter_client import OpenRouterClient, DEFAULT_MODEL

logger = logging.getLogger('CCSubsPro.AI')

SYSTEM_PROMPT = """Eres un editor de video profesional y especialista en retención para contenido corto (Reels, TikTok, Shorts).
Tu tarea es analizar los subtítulos de un video y decidir QUÉ palabras o frases breves deben destacarse visualmente para maximizar la atención y retención del espectador.

REGLAS CRÍTICAS:
1. CADENCIA CONSTANTE Y DINÁMICA: Destaca palabras con buena frecuencia (aproximadamente cada 3 a 4 segundos, o cada 2 a 3 subtítulos) para mantener el ritmo visual y dinamismo del video.
2. Destaca entre 1 y 3 palabras por subtítulo, o una frase corta con alto impacto.
3. Si un subtítulo es solo una muletilla o conector vacío ("de que un", "y me dicen", "decir"), deja la lista "phrases" vacía [].
4. PRIORIZA:
   - Conceptos clave, términos anatómicos/médicos, números importantes o advertencias.
   - Términos emocionalmente relevantes o palabras de problema/dolor/error.
   - Palabras que resumen la idea principal de la frase.
5. NO DESTAQUES (REGLA DE UNIDAD SEMÁNTICA):
   - JAMÁS la palabra "no". La palabra "no" NUNCA se destaca bajo ninguna circunstancia (si una frase dice "no improvisas", destaca ÚNICAMENTE "improvisas").
   - JAMÁS palabras de 1 o 2 letras ("no", "el", "la", "o", "y", "un", "de", "en", "se", "es", "al", "me", "te", "le", "lo", "su", "mi", "si", "ya", "ni").
   - JAMÁS palabras vacías o conectores cortos como "así", "asi", "bien", "muy", "tan", "más", "cada".
   - Artículos (el, la, los, las, un, una).
   - Preposiciones solas (de, en, con, por, para, sin).
   - Conectores o conjunciones (porque, pero, cuando, como, que, si, donde, mientras, pues, ya, sino, entonces). JAMÁS destaques "porque".
   - Verbos auxiliares o muletillas aisladas (decir, hace, estar, ser).
   - NUNCA repitas la misma palabra destacada múltiples veces.
   - NUNCA unas una palabra destacada con la palabra siguiente si pertenecen a partes distintas de la oración (por ejemplo: JAMÁS un sustantivo o adjetivo junto con el verbo que inicia la siguiente frase, como "lingual forman", "bebé duerme", "niño llora").
   - NUNCA unas palabras con conectores, conjunciones o preposiciones siguientes (como "dolor cuando", "problema que", "cirugía pero", "ojos porque").
   - Si destacas una frase de 2 palabras, DEBE ser un concepto unitario inseparable (como "suelo pélvico", "movilidad lingual"). En caso de duda, destaca ÚNICAMENTE una sola palabra clave.
6. CADA frase devuelta en "phrases" DEBE coincidir EXACTAMENTE con el texto del subtítulo.

DEBES RESPONDER EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO CON ESTE FORMATO:
{
  "highlights": [
    {
      "subtitle_id": "ID_CAPCUT",
      "phrases": ["palabra o frase destacada"]
    }
  ]
}
"""

class AIHighlighter:
    def __init__(self, api_key: Optional[str] = None, provider: str = 'auto', model: Optional[str] = None):
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY') or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or os.environ.get('OPENAI_API_KEY')
        self.provider = provider
        self.model = model
        
        if self.provider == 'auto':
            if self.api_key and (self.api_key.startswith('sk-or-') or os.environ.get('OPENROUTER_API_KEY')):
                self.provider = 'openrouter'
            elif os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY'):
                self.provider = 'gemini'
            elif os.environ.get('OPENAI_API_KEY'):
                self.provider = 'openai'
            elif self.api_key:
                # If key provided without prefix, default to openrouter if it looks like an openrouter key or gemini
                self.provider = 'openrouter'
            else:
                self.provider = 'heuristic'

    def get_highlights(self, subtitles: List[Dict[str, str]]) -> Dict[str, List[str]]:
        if not subtitles:
            return {}

        if self.provider == 'openrouter' and self.api_key:
            res = self._call_openrouter(subtitles)
            if res:
                return res
        elif self.provider == 'gemini' and self.api_key:
            res = self._call_gemini(subtitles)
            if res:
                return res
        elif self.provider == 'openai' and self.api_key:
            res = self._call_openai(subtitles)
            if res:
                return res

        logger.info('Using heuristic rule-based highlighter (offline fallback).')
        return self._heuristic_highlighter(subtitles)

    def _call_openrouter(self, subtitles: List[Dict[str, str]]) -> Optional[Dict[str, List[str]]]:
        model_name = self.model or DEFAULT_MODEL
        client = OpenRouterClient(api_key=self.api_key, model=model_name)
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Subtítulos:\n{json.dumps(subtitles, ensure_ascii=False, indent=2)}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key.strip()}',
                    'HTTP-Referer': 'https://ccsubspro.local',
                    'X-Title': 'CC Subs Pro'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                raw_text = data['choices'][0]['message']['content']
                parsed = json.loads(raw_text)
                return self._parse_ai_response(parsed)
        except Exception as e:
            logger.error(f'OpenRouter API error: {e}')
            return None

    def _call_gemini(self, subtitles: List[Dict[str, str]]) -> Optional[Dict[str, List[str]]]:
        model_name = self.model or 'gemini-1.5-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        
        prompt_content = f"{SYSTEM_PROMPT}\n\nSubtítulos a procesar:\n{json.dumps(subtitles, ensure_ascii=False, indent=2)}"
        payload = {
            "contents": [{"parts": [{"text": prompt_content}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                raw_text = data['candidates'][0]['content']['parts'][0]['text']
                parsed = json.loads(raw_text)
                return self._parse_ai_response(parsed)
        except Exception as e:
            logger.error(f'Gemini API error: {e}')
            return None

    def _call_openai(self, subtitles: List[Dict[str, str]]) -> Optional[Dict[str, List[str]]]:
        base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        url = f"{base_url}/chat/completions"
        model_name = self.model or 'gpt-4o-mini'
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Subtítulos:\n{json.dumps(subtitles, ensure_ascii=False, indent=2)}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                raw_text = data['choices'][0]['message']['content']
                parsed = json.loads(raw_text)
                return self._parse_ai_response(parsed)
        except Exception as e:
            logger.error(f'OpenAI API error: {e}')
            return None

    def _parse_ai_response(self, response_json: Dict[str, Any]) -> Dict[str, List[str]]:
        result = {}
        items = response_json.get('highlights', [])
        for item in items:
            sid = item.get('subtitle_id')
            phrases = item.get('phrases', [])
            if sid and isinstance(phrases, list):
                result[sid] = [sanitize_highlight_phrase(str(p)) for p in phrases if sanitize_highlight_phrase(str(p))]
        return result

    def suggest_highlights(self, script_text: str, count: int = 25) -> List[str]:
        cleaned_script = clean_subtitle_text(script_text)
        stopwords = {
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
            'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'si', 'como', 'cuando',
            'yo', 'tu', 'él', 'ella', 'nosotros', 'vosotros', 'ellos', 'ellas', 'me', 'te', 'se', 'nos', 'os',
            'mi', 'tu', 'su', 'mis', 'tus', 'sus', 'es', 'son', 'fue', 'era', 'hay', 'muy', 'más',
            'decir', 'hace', 'hacer', 'tener', 'tienes', 'ser', 'estar', 'está', 'están', 'vamos', 'dice',
            'pueden', 'sido', 'hecho', 'ahora', 'después', 'entonces', 'aquí', 'allí', 'bueno', 'bien'
        }

        # Look for 2-word phrases first with strict semantic boundary verification
        words = [w for w in re.findall(r'\b[\wáéíóúÁÉÍÓÚñÑüÜ]+\b', cleaned_script)]
        phrases = []
        for i in range(len(words) - 1):
            w1 = words[i].lower()
            w2 = words[i+1].lower()
            if (w1 not in stopwords and w2 not in stopwords and 
                w1 not in INVALID_LEADING_HIGHLIGHT_WORDS and w2 not in INVALID_TRAILING_HIGHLIGHT_WORDS and
                len(w1) > 3 and len(w2) > 3):
                cand_phrase = f"{words[i]} {words[i+1]}"
                san = sanitize_highlight_phrase(cand_phrase)
                if san and len(san.split()) == 2:
                    phrases.append(san)

        # Individual candidates
        single_candidates = [w for w in words if w.lower() not in stopwords and len(w) > 4]

        seen = set()
        chosen = []

        # Interleave phrases and singles
        for p in phrases:
            clean_p = clean_subtitle_text(p)
            if clean_p.lower() not in seen:
                seen.add(clean_p.lower())
                chosen.append(clean_p)
            if len(chosen) >= count:
                break

        if len(chosen) < count:
            for s in single_candidates:
                clean_s = clean_subtitle_text(s)
                if clean_s.lower() not in seen:
                    seen.add(clean_s.lower())
                    chosen.append(clean_s)
                if len(chosen) >= count:
                    break

        return chosen

    def _heuristic_highlighter(self, subtitles: List[Dict[str, str]]) -> Dict[str, List[str]]:
        result = {}
        seen_highlights = set()
        for sub in subtitles:
            sid = sub['subtitle_id']
            text = clean_subtitle_text(sub['text'])
            words = [w for w in re.findall(r'\b[\wáéíóúÁÉÍÓÚñÑüÜ]+\b', text)]
            candidates = [w for w in words if w.lower() not in SPANISH_STOPWORDS and len(w) > 3 and w.lower() not in seen_highlights]
            if candidates:
                chosen = [candidates[-1]]
                seen_highlights.add(candidates[-1].lower())
                result[sid] = chosen
            else:
                result[sid] = []
        return result
