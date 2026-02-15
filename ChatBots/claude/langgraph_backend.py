from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

# connection object
from sqlite_db import conn

load_dotenv()

# State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # list of messages with reducer 

# Model
llm = ChatOpenAI(model='gpt-4o-mini')

# Nodes
def chat_node(state: ChatState):
    message = state['messages']
    response = llm.invoke(message)
    return {'messages': [response]}


# Checkpointer
checkpointer = SqliteSaver(conn=conn)

# Creating Graph
graph = StateGraph(ChatState)

graph.add_node('chat_node', chat_node)

graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatBot = graph.compile(checkpointer=checkpointer)


# Extract all threads
def retrieve_all_threads():
    """Retrieve all thread IDs from the database"""
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])
    return list(all_threads)
