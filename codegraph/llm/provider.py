"""
-------------------------------
LLM Provider Interface (LiteLLM)
-------------------------------

This module provides an interface for accessing different LLM providers
through LiteLLM. It also handles retries and response parsing.
"""
import json
import re
import time
from typing import Dict, Any, Optional, List
import logging
from abc import ABC, abstractmethod

# Import LiteLLM for multi-provider support
import litellm
from litellm import completion

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def query(self, prompt: str) -> str:
        """
        Send a prompt to the LLM and return the response.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a string
        """
        pass

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """
        Extract a JSON object from the LLM response.

        Args:
            text: The LLM response text

        Returns:
            The extracted JSON as a dictionary
        """
        # First try to find a JSON code block
        match = re.search(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Then try to find any JSON-like structure
            match = re.search(r"({[\s\S]*})", text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # Error if we cannot find any JSON
                raise ValueError("Could not extract JSON from response")

        return json.loads(json_str)


class LiteLLMProvider(LLMProvider):
    """
    An Provider for LiteLLM-supported LLMs.
    """

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 10,
        temperature: float = 0.1,
    ):
        """
        Initialize a new LiteLLM provider.

        Args:
            model_name: The name of the model to use
            api_key: The API key for the model provider
            max_retries: Maximum number of retries on rate limit errors
            retry_delay: Delay in seconds between retries
            temperature: Temperature parameter for the model
        """
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.temperature = temperature

        if api_key:
            # Configure LiteLLM with the provided API key
            # This can be extended to handle different provider API keys
            if (
                "gpt-4" in model_name.lower()
                or model_name.startswith("o1")
                or model_name.startswith("o3")
            ):
                litellm.openai_api_key = api_key
            elif "claude" in model_name.lower():
                litellm.anthropic_api_key = api_key
            elif "google" in model_name.lower():
                litellm.google_api_key = api_key
            elif "gemini" in model_name.lower():
                litellm.gemini_api_key = api_key
            else:
                # Default fallback
                # Handles a variety of api keys
                litellm.api_key = api_key

    def query(self, prompt: str) -> str:
        """
        Send a prompt to the LLM with retry logic for rate limits.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a string

        Raises:
            Exception: If maximum retries are exceeded
        """
        retries = 0
        last_error = None

        while retries < self.max_retries:
            try:
                response = completion(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if any(
                    err in error_str.lower()
                    for err in ["429", "rate limit", "ratelimit", "throttle"]
                ):
                    logger.warning(
                        f"Rate limit error, retrying in {self.retry_delay} seconds: {e}"
                    )
                    time.sleep(self.retry_delay)
                    retries += 1
                else:
                    # Re-raise any other errors
                    logger.error(f"LLM query error: {e}")
                    raise

        # If we've exhausted retries, raise the last error
        logger.error(f"Max retries exceeded in LLM query: {last_error}")
        raise Exception(f"Max retries exceeded: {last_error}")


class LLMProviderFactory:
    """Factory for creating LLM providers based on model name."""

    @staticmethod
    def create_provider(
        model_name: str, api_key: Optional[str] = None, **kwargs
    ) -> LLMProvider:
        """
        Create an LLM provider based on the model name.

        Args:
            model_name: The name of the model to use
            api_key: The API key for the model provider
            **kwargs: Additional arguments to pass to the provider

        Returns:
            An LLM provider instance
        """
        return LiteLLMProvider(model_name, api_key, **kwargs)


# -- Example Usage --


def main():
    import os

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Set test parameters (replace with your configuration)
    model_name = "gemini/gemini-2.0-flash-exp"
    api_key = os.environ["GEMINI_API_KEY"]
    test_prompt = "What is the capital of France?"

    # Create LLM provider instance
    provider = LLMProviderFactory.create_provider(
        model_name, api_key, max_retries=2, retry_delay=5, temperature=0.7
    )

    try:
        # Query the LLM
        response = provider.query(test_prompt)
        print("LLM Response:", response)

        # Test JSON extraction (Assuming model returns JSON)
        json_response = provider.extract_json('{"answer": "Paris"}')
        print("Extracted JSON:", json_response)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
