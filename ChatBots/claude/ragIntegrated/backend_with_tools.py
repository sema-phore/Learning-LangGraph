import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition


from utility_tools import search_tool, get_stock_price, calculator, rag_tool

load_dotenv()

#--------------- Langsmith project name -----------------------
os.environ["LANGSMITH_PROJECT"] = "Chatbot-Project"



# ------------------ sqlite connection object --------------
from sqlite_db import conn



# -------------- Tools Integration -----------------
tools = [search_tool, get_stock_price, calculator, rag_tool]



# ----------------- Models ------------------------
llm = ChatOpenAI(model='gpt-4o-mini')
llm_with_tools = llm.bind_tools(tools)


# --------------- Graph State ----------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # list of messages with reducer 


# --------------- Graph Nodes --------------------
def chat_node(state: ChatState):
    message = state['messages']
    response = llm_with_tools.invoke(message) # LLM with tools
    return {'messages': [response]}

tool_node = ToolNode(tools)


# ---------------- Checkpointer -------------------
checkpointer = SqliteSaver(conn=conn)

# --------------- Creating Graph ------------------
graph = StateGraph(ChatState)

graph.add_node('chat_node', chat_node)
graph.add_node('tools', tool_node)

graph.add_edge(START, 'chat_node')
graph.add_conditional_edges('chat_node', tools_condition)
graph.add_edge('tools', 'chat_node')

chatBot = graph.compile(checkpointer=checkpointer)

# --------------- Healper --------------------------
# Extract all threads
def retrieve_all_threads():
    """Retrieve all thread IDs from the database"""
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])
    return list(all_threads)
