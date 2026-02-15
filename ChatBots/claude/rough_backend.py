from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

load_dotenv()

# State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages] # list of messages with reducer 

# Model
llm = ChatOpenAI()

# Nodes
def chat_node(state: ChatState):
    message = state['messages']

    response = llm.invoke(message)

    return {'messages': [response]}

# Database
conn = sqlite3.connect(database='chatbot.db', check_same_thread=False)
#Checkpointer
checkpointer = SqliteSaver(conn=conn)


# Creating Graph
graph = StateGraph(ChatState)

graph.add_node('chat_node', chat_node)

graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatBot = graph.compile(checkpointer=checkpointer)

# Extrack No of threads
def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])
        
    return list(all_threads)
