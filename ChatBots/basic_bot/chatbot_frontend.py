import streamlit as st
from chatbot_backend import chatBot
from langchain_core.messages import HumanMessage

CONFIG = {'configurable': {'thread_id': 'thread_1'}}

# Create a session state to store the messages
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# load all messages
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input('Type here ')

if user_input:
    st.session_state['message_history'].append({'role':'user', 'content':user_input})
    with st.chat_message('user'):
        st.text(user_input)

    # ChatBot reply
    response = chatBot.invoke({'messages': [HumanMessage(content=user_input)]}, config=CONFIG)
    bot_output = response['messages'][-1].content
    st.session_state['message_history'].append({'role':'assistant', 'content': bot_output})
    with st.chat_message('assistant'):
        st.text(bot_output)