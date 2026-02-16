import streamlit as st
from langgraph_backend import chatBot
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlite_db import save_thread_metadata


# **************************************** utility functions ***************************************
from streamlit_utility_functions import (
    generate_thread_id, 
    reset_chat, add_thread, 
    load_conversation, 
    generate_conversation_name, 
    load_threads_from_database
)


# ***************************************** Session states *****************************************

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state['initialized'] = False

# List to store thread ids - load from database first
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

# Load existing threads from database on first run
if not st.session_state['initialized']:
    existing_threads = load_threads_from_database()
    st.session_state['chat_threads'] = existing_threads
    st.session_state['initialized'] = True

# Thread ID - use existing or create new
if 'thread_id' not in st.session_state:
    if st.session_state['chat_threads']:
        # Use the most recent thread
        st.session_state['thread_id'] = st.session_state['chat_threads'][0]['id']
    else:
        # Create a new thread
        st.session_state['thread_id'] = generate_thread_id()
        add_thread(st.session_state['thread_id'])

# Create a session state to store the messages
if 'message_history' not in st.session_state:
    # Load messages from the current thread
    messages = load_conversation(st.session_state['thread_id'])
    temp_messages = []
    
    if messages:
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = 'user'
            else:
                role = 'assistant'
            temp_messages.append({'role': role, 'content': msg.content})
    
    st.session_state['message_history'] = temp_messages


# ******************************************* Sidebar UI ******************************************

st.sidebar.title('Resume ChatBot')

# New Chat
if st.sidebar.button('New Chat'):
    reset_chat()
    st.rerun()

st.sidebar.header('My Conversations')

# Display all conversations
for thread in st.session_state['chat_threads'][::-1]:
    thread_id = thread['id']
    name = thread['name']
    
    if st.sidebar.button(name, key=thread_id):
        # Switch to this thread
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []

        # Only process if there are messages
        if messages:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    role = 'user'
                else:
                    role = 'assistant'
                temp_messages.append({'role': role, 'content': msg.content})
        
        st.session_state['message_history'] = temp_messages
        st.rerun()


# ******************************************** Main UI ********************************************

# Load all messages
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

user_input = st.chat_input('Type here')

if user_input:
    # Store the user message
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.markdown(user_input)

    # Stream the assistant response
    CONFIG = {
        "configurable": {"thread_id": st.session_state["thread_id"]},
        "metadata":{"thread_id": st.session_state["thread_id"]},
        "run_name": "chat_turn"
        }


    with st.chat_message('assistant'):
        # Mutable holder so the generator can set/modify it
        status_holder = {"box": None}

        def ai_only_stream():
            for message_chunk, metadata in chatBot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages'
            ):
                # status container for tool runs
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …",
                            expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )

                # Stream only assistant token
                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

        # Finalize only if a tool was actually used
        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    # Store the message
    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
    
    # Get current thread
    current_thread = None
    for thread in st.session_state['chat_threads']:
        if thread['id'] == st.session_state['thread_id']:
            current_thread = thread
            break
    
    # Only generate name if:
    # 1. Thread hasn't been named yet
    # 2. There are at least 3 messages
    if current_thread and not current_thread.get('named', False) and len(st.session_state['message_history']) >= 3:
        try:
            name = generate_conversation_name(
                st.session_state['message_history'], 
                st.session_state['thread_id']
            )
            current_thread['name'] = name
            current_thread['named'] = True
            
            # Save to database so it persists across sessions
            save_thread_metadata(st.session_state['thread_id'], name, True)
            
        except Exception as e:
            print(f"Error generating name: {e}")
    
    st.rerun()
