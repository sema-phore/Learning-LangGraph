import requests
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from typing import Optional


from rag_utility import (
    get_thread_metadata,
    _get_retriever, 

)


# ---------------RAG Tools --------------------
@tool
def rag_tool(query: str, thread_id: Optional[str] = None) -> dict:
    """
    Retrive the relevent informations from the uploaded PDF/Document for this chat thread based on the query.
    Always include the thread_id when calling this tool.
    """

    retriever = _get_retriever(thread_id)
    if retriever is None:
        return {
            "error": "No relavent document indexed fot this chat. Upload the PDF first",
            "query":query
            }
    
    result = retriever.invoke(query)
    context = [doc.page_content for doc in result]
    metadata = [doc.metadata for doc in result]
    source_file = get_thread_metadata(str(thread_id)).get("filename")
    return {
        "query": query,
        "context": context,
        "metadata": metadata,
        "source_file": source_file
    }



# -------------- Normal Tools -----------------
# Search Tool
search_tool = DuckDuckGoSearchRun(region='us-en')

# Stock price tool
@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=JPN8957QA6A861KZ"
    r = requests.get(url)
    return r.json()

# Calculator tool
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}
