from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages] # list of messages with reducer 

# Model
llm = ChatOpenAI(model='gpt-4o-mini')

# Nodes
def chat_node(state: ChatState):
    message = state['messages']

    response = llm.invoke(message)

    return {'messages': [response]}

# Creating Graph
graph = StateGraph(ChatState)
checkpointer = MemorySaver()

graph.add_node('chat_node', chat_node)

graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatBot = graph.compile(checkpointer=checkpointer)
