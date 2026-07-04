"""Shared LLM access for ALL agents: Gemini primary, Groq backup."""
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq


def _gemini():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=st.secrets["GEMINI_API_KEY"],
        temperature=0,   # agents want consistency, not creativity
    )


def _groq():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=st.secrets["GROQ_API_KEY"],
        temperature=0,
    )


def ask_llm(prompt: str) -> str:
    """Try Gemini; on rate-limit/failure, retry once on Groq."""
    try:
        reply = _gemini().invoke(prompt)
        print("[llm] answered by: gemini")
        return reply.content
    except Exception as e:
        print(f"[llm] gemini failed ({type(e).__name__}), falling back to groq")
        reply = _groq().invoke(prompt)
        print("[llm] answered by: groq")
        return reply.content


if __name__ == "__main__":
    # smoke test: run `python -m src.llm`
    print(ask_llm("Reply with exactly: WRAPPER OK"))