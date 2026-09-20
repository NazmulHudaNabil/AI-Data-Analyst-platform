from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv


load_dotenv()


def pick_llm(level: str):
    """
    Pick a language model based on the provided model name.

    Args:
        model_name (str): The name of the model to pick.

    Returns:
        An instance of the selected language model.
    """
    if level == "low":
        llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
    elif level == "medium":
        llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0)
    elif level == "high":
        llm = ChatGoogleGenerativeAI(model="gemini-3.1-pro-preview", temperature=0)
    else:
        raise ValueError(f"Invalid level: {level}. Choose from 'low', 'medium', or 'high'.")
    return llm

