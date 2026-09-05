"""
Pytest configuration — sets env vars so tests work without a real PostgreSQL instance.
"""
import os
import pytest

# Set environment before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_polar_ai.db")
os.environ.setdefault("DATA_MODE", "demo")
os.environ.setdefault("DEMO_RANDOM_SEED", "42")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
