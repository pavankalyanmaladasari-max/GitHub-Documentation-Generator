"""
Multi-provider inference engine.
Supports OpenAI, Google Gemini, and Hugging Face with heuristic fallbacks.
"""

from typing import Optional
import os

import requests

try:
    from huggingface_hub import InferenceClient
    HAS_HF_HUB = True
except ImportError:
    HAS_HF_HUB = False


class LocalInferenceEngine:
    """Uses configured AI providers for intelligent content generation."""
    
    # Best models for code understanding and text generation
    HF_MODELS = [
        "meta-llama/Llama-3.1-8B-Instruct",      # Verified working with this token
        "meta-llama/Meta-Llama-3-8B-Instruct",   # Alternative instruct model
        "Qwen/Qwen2.5-7B-Instruct",              # Strong instruction model
        "mistralai/Mistral-7B-Instruct-v0.2",    # Fallback if provider supports it
    ]
    
    def __init__(self, api_token: Optional[str] = None, provider: Optional[str] = None):
        """
        Initialize the inference engine with the configured AI provider.
        
        Args:
            api_token: Provider token override. If None, tries secrets.toml or env.
            provider: Provider override. Supported: openai, gemini, huggingface.
        """
        settings = self._load_settings()
        self.provider = (provider or settings["provider"] or "").lower() or None
        self.api_token = api_token or settings["token"]
        self.client = None
        self.current_model = settings["model"]
        self.reason = None
        self._provider_temporarily_disabled = False
        self._last_error_signature = None
        self.initialize_models()

    def _log_once(self, message: str) -> None:
        """Log a provider error only once per unique message to avoid console spam."""
        if message != self._last_error_signature:
            print(message)
            self._last_error_signature = message

    def _disable_provider(self, reason: str) -> None:
        """Disable provider for the current process after fatal API errors."""
        self.reason = reason
        self.client = None
        self._provider_temporarily_disabled = True
    
    def _load_settings(self) -> dict:
        """Load provider settings from secrets.toml or environment."""
        secrets = {}

        try:
            import toml
            current_dir = os.path.dirname(os.path.abspath(__file__))
            secrets_path = os.path.join(current_dir, ".streamlit", "secrets.toml")
            
            if os.path.exists(secrets_path):
                secrets = toml.load(secrets_path)
        except Exception as e:
            print(f"Warning: Could not load secrets.toml: {e}")

        provider = (os.getenv("AI_PROVIDER") or secrets.get("AI_PROVIDER") or "").lower() or None

        openai_key = os.getenv("OPENAI_API_KEY") or secrets.get("OPENAI_API_KEY")
        gemini_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or secrets.get("GEMINI_API_KEY")
            or secrets.get("GOOGLE_API_KEY")
        )
        hf_key = (
            os.getenv("HF_API_TOKEN")
            or os.getenv("HUGGINGFACE_TOKEN")
            or os.getenv("HF_TOKEN")
            or secrets.get("HF_API_TOKEN")
        )

        openai_model = os.getenv("OPENAI_MODEL") or secrets.get("OPENAI_MODEL") or "gpt-4o-mini"
        gemini_model = os.getenv("GEMINI_MODEL") or secrets.get("GEMINI_MODEL") or "gemini-1.5-pro"

        providers = {
            "openai": {"token": openai_key, "model": openai_model},
            "gemini": {"token": gemini_key, "model": gemini_model},
            "huggingface": {"token": hf_key, "model": None},
        }

        if provider in providers:
            return {
                "provider": provider,
                "token": providers[provider]["token"],
                "model": providers[provider]["model"],
            }

        for candidate in ("openai", "gemini", "huggingface"):
            if providers[candidate]["token"]:
                return {
                    "provider": candidate,
                    "token": providers[candidate]["token"],
                    "model": providers[candidate]["model"],
                }
        
        return {"provider": None, "token": None, "model": None}
    
    def initialize_models(self):
        """Initialize the configured provider."""
        if not self.provider:
            self.reason = "No AI provider configured"
            return

        if not self.api_token:
            self.reason = f"Missing API key for provider '{self.provider}'"
            return

        if self.provider == "openai":
            self.client = "openai"
            self.current_model = self.current_model or "gpt-4o-mini"
            print(f"✓ Using OpenAI model: {self.current_model}")
            return

        if self.provider == "gemini":
            self.client = "gemini"
            self.current_model = self.current_model or "gemini-1.5-pro"
            print(f"✓ Using Gemini model: {self.current_model}")
            return

        if self.provider != "huggingface":
            self.reason = f"Unsupported AI provider '{self.provider}'"
            return

        if not HAS_HF_HUB:
            self.reason = "huggingface_hub library not installed"
            print("Warning: huggingface_hub not installed. Using fallback methods.")
            return

        try:
            self.client = InferenceClient(token=self.api_token)

            for model in self.HF_MODELS:
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "Say OK"}],
                        max_tokens=6,
                        temperature=0.0,
                    )
                    if response:
                        self.current_model = model
                        print(f"✓ Using HuggingFace model: {model}")
                        self.reason = None
                        return
                except Exception as e:
                    print(f"  Model {model}: {str(e)[:100]}")
                    continue
        except Exception as e:
            self.reason = f"Could not initialize HuggingFace client: {e}"
            print(f"Warning: Could not initialize HF client: {e}")
        
        self.reason = self.reason or "Could not connect to HuggingFace API"
        print("Warning: Could not connect to HuggingFace API. Using fallback methods.")
        self.client = None

    def is_available(self) -> bool:
        """Return True when an AI provider is configured and ready."""
        return bool(
            not self._provider_temporarily_disabled
            and self.client
            and self.current_model
            and self.provider
        )
    
    def _query(self, prompt: str, max_length: int = 150) -> Optional[str]:
        """
        Query the configured AI provider.
        
        Args:
            prompt: Input text
            max_length: Maximum response length
            
        Returns:
            Generated text or None
        """
        if not self.is_available():
            return None

        if self.provider == "openai":
            return self._query_openai(prompt, max_length)

        if self.provider == "gemini":
            return self._query_gemini(prompt, max_length)

        return self._query_huggingface(prompt, max_length)

    def _query_openai(self, prompt: str, max_length: int) -> Optional[str]:
        """Query OpenAI Chat Completions API."""
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.current_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_length,
                    "temperature": 0.3,
                },
                timeout=60,
            )
            if response.status_code != 200:
                error_excerpt = response.text[:180]
                self.reason = f"OpenAI API error {response.status_code}: {error_excerpt}"

                # Quota/rate-limit errors should stop further attempts to avoid noisy logs.
                if response.status_code in (429, 402):
                    self._disable_provider(
                        "OpenAI quota or rate limit reached. AI calls are temporarily disabled; static analysis remains available."
                    )
                    self._log_once(self.reason)
                    return None

                self._log_once(self.reason)
                return None

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if isinstance(content, list):
                return " ".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ).strip() or None
            if isinstance(content, str):
                return content.strip() or None
        except Exception as e:
            self.reason = f"OpenAI query failed: {str(e)[:120]}"
            self._log_once(self.reason)

        return None

    def _query_gemini(self, prompt: str, max_length: int) -> Optional[str]:
        """Query Google Gemini generateContent API."""
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.current_model}:generateContent?key={self.api_token}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": max_length,
                    },
                },
                timeout=60,
            )
            if response.status_code != 200:
                self.reason = f"Gemini API error {response.status_code}: {response.text[:120]}"
                print(self.reason)
                return None

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
            result = "\n".join(part for part in text_parts if part).strip()
            return result or None
        except Exception as e:
            self.reason = f"Gemini query failed: {str(e)[:120]}"
            print(self.reason)

        return None

    def _query_huggingface(self, prompt: str, max_length: int) -> Optional[str]:
        """Query Hugging Face Inference API."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_length,
                temperature=0.3,
            )

            if response and response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    return content.strip()

        except Exception as e:
            try:
                response = self.client.text_generation(
                    prompt,
                    model=self.current_model,
                    max_new_tokens=max_length,
                    temperature=0.3,
                    return_full_text=False
                )
                if response and isinstance(response, str):
                    return response.strip()
            except Exception:
                print(f"Error querying model: {str(e)[:100]}")
        
        return None
    
    def generate_function_description(self, function_info: dict) -> str:
        """
        Generate a detailed description of a function using HuggingFace API.
        
        Args:
            function_info: Dictionary containing function details
            
        Returns:
            str: Detailed description of the function's purpose
        """
        try:
            func_name = function_info.get("name", "function")
            params = function_info.get("params", {})
            returns = function_info.get("returns", "")
            docstring = function_info.get("docstring", "")
            language = function_info.get("language", "")
            
            # Build a prompt for the model
            param_str = ", ".join(params.keys()) if params else "no parameters"
            
            prompt = f"""Describe what this {language} function does in 1-2 clear sentences:
Function: {func_name}({param_str})
Returns: {returns if returns else 'unknown'}
{f'Docstring: {docstring[:200]}' if docstring else ''}

Description:"""
            
            result = self._query(prompt, max_length=100)
            
            if result and len(result) > 10:
                return result
        except Exception as e:
            print(f"Error generating description: {e}")
        
        return self._fallback_description(function_info)
    
    def generate_file_summary(self, file_info: dict) -> str:
        """
        Generate a comprehensive summary of a file's purpose.
        
        Args:
            file_info: File analysis dictionary
            
        Returns:
            str: Summary of the file's purpose
        """
        try:
            file_path = file_info.get("file_path", "file.js")
            language = file_info.get("language", "Unknown")
            classes = file_info.get("classes", [])
            functions = file_info.get("functions", [])
            imports = file_info.get("imports", [])
            
            class_str = ", ".join(classes[:3]) if classes else "none"
            func_str = ", ".join(f['name'] for f in functions[:3] if isinstance(f, dict)) if functions else "none"
            
            prompt = f"""Describe what this {language} source file does in 2-3 sentences:
File: {file_path}
Classes: {class_str}
Functions: {func_str}
Key imports: {', '.join(str(i)[:30] for i in imports[:5]) if imports else 'standard'}

Summary:"""
            
            result = self._query(prompt, max_length=150)
            
            if result and len(result) > 10:
                return result
        except Exception as e:
            print(f"Error generating file summary: {e}")
        
        return self._fallback_file_summary(file_info)
    
    def generate_class_description(self, class_info: dict) -> str:
        """
        Generate a detailed description of a class.
        
        Args:
            class_info: Dictionary containing class details
            
        Returns:
            str: Detailed description of the class
        """
        try:
            class_name = class_info.get("name", "Class")
            methods = class_info.get("methods", [])
            properties = class_info.get("properties", [])
            
            method_str = ", ".join(methods[:5]) if methods else "none"
            prop_str = ", ".join(properties[:5]) if properties else "none"
            
            prompt = f"""Describe the purpose of this class in 1-2 sentences:
Class: {class_name}
Methods: {method_str}
Properties: {prop_str}

Purpose:"""
            
            result = self._query(prompt, max_length=80)
            
            if result and len(result) > 10:
                return result
        except Exception as e:
            print(f"Error generating class description: {e}")
        
        return self._fallback_class_description(class_info)
    
    @staticmethod
    def _fallback_description(function_info: dict) -> str:
        """Fallback description when model is unavailable."""
        func_name = function_info.get("name", "function")
        params = function_info.get("params", {})
        returns = function_info.get("returns", "")
        docstring = function_info.get("docstring", "")
        
        description = f"The '{func_name}' function"
        
        if params:
            description += f" accepts {len(params)} parameter(s)"
        
        if returns:
            description += f" and returns {returns}"
        
        if docstring:
            description += f". {docstring[:100]}"
        else:
            description += " performs specific operations within the codebase."
        
        return description
    
    @staticmethod
    def _fallback_file_summary(file_info: dict) -> str:
        """Fallback file summary when model is unavailable."""
        file_path = file_info.get("file_path", "file")
        language = file_info.get("language", "Unknown")
        classes = file_info.get("classes", [])
        functions = file_info.get("functions", [])
        
        parts = file_path.split("/")
        file_name = parts[-1] if parts else file_path
        
        summary = f"This {language} file ({file_name}) contains "
        
        if classes:
            summary += f"{len(classes)} class(es)"
            if functions:
                summary += f" and {len(functions)} function(s)"
        elif functions:
            summary += f"{len(functions)} function(s)"
        else:
            summary += "utility code"
        
        summary += " for the project."
        return summary
    
    @staticmethod
    def _fallback_class_description(class_info: dict) -> str:
        """Fallback class description when model is unavailable."""
        class_name = class_info.get("name", "Class")
        methods = class_info.get("methods", [])
        
        desc = f"The {class_name} class"
        if methods:
            desc += f" provides {len(methods)} method(s) for"
        else:
            desc += " defines"
        
        desc += " core functionality in the codebase."
        return desc


# Global instance
_inference_engine = None


def get_inference_engine() -> LocalInferenceEngine:
    """Get or create the global inference engine instance."""
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = LocalInferenceEngine()
    return _inference_engine


def generate_function_description(function_info: dict) -> str:
    """Generate description for a function."""
    engine = get_inference_engine()
    return engine.generate_function_description(function_info)


def generate_file_summary(file_info: dict) -> str:
    """Generate summary for a file."""
    engine = get_inference_engine()
    return engine.generate_file_summary(file_info)


def generate_class_description(class_info: dict) -> str:
    """Generate description for a class."""
    engine = get_inference_engine()
    return engine.generate_class_description(class_info)


def generate_repo_summary(repo_info: dict) -> str:
    """
    Generate an intelligent summary of the entire repository.
    
    Args:
        repo_info: Dictionary containing repository metrics
        
    Returns:
        str: Summary of the repository's purpose and structure
    """
    try:
        total_files = repo_info.get("total_source_files", 0)
        total_functions = repo_info.get("total_functions", 0)
        total_classes = repo_info.get("total_classes", 0)
        top_files = repo_info.get("top_function_files", [])
        
        engine = get_inference_engine()
        
        # Build prompt for AI model
        top_files_str = ", ".join(top_files[:3]) if top_files else "various"
        prompt = f"""Summarize what this repository does in 1-2 sentences:
Total Files: {total_files}
Total Functions: {total_functions}
Total Classes: {total_classes}
Key Files: {top_files_str}

Summary:"""
        
        result = engine._query(prompt, max_length=120) if engine.is_available() else None
        
        if result and len(result) > 20:
            return result
    except Exception as e:
        print(f"Error generating repo summary: {e}")
    
    # Fallback summary
    parts = []
    if total_files:
        parts.append(f"{total_files} source files")
    if total_classes:
        parts.append(f"{total_classes} classes")
    if total_functions:
        parts.append(f"{total_functions} functions")
    
    if parts:
        return f"This repository contains {', '.join(parts)} organized across multiple modules."
    return "A software project with multiple code files and components."


def get_model_status() -> dict:
    """
    Get the current status of the inference model.
    
    Returns:
        dict: Status dictionary with keys:
            - provider: Active AI provider
            - model: Current model name (or None if unavailable)
            - available: Boolean indicating whether AI is ready
            - hf_disabled: Backwards-compatible unavailable flag
            - reason: Reason if disabled
    """
    engine = get_inference_engine()
    
    status = {
        "provider": engine.provider,
        "model": engine.current_model,
        "available": engine.is_available(),
        "hf_disabled": not engine.is_available(),
        "reason": engine.reason,
    }

    if not status["available"] and not status["reason"]:
        status["reason"] = "Set OPENAI_API_KEY, GEMINI_API_KEY, or HF_API_TOKEN"

    return status
