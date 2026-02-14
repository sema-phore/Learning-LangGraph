import streamlit as st
from langgraph_backend import chatBot
from langchain_core.messages import HumanMessage
import uuid # to generate thread id


# **************************************** utility funtions ***************************************

# Generate a thread ID
def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id


# Reset chat
def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []

# store threads
def add_thread(thread_id):
    if not any(thread['id'] == thread_id for thread in st.session_state['chat_threads']):
        thread = {
            "id":thread_id, 
            "name": "New Chat",
            "named": False}
        st.session_state['chat_threads'].append(thread)

# restore conversesstion
def load_conversation(thread_id):
    CONFIG = {'configurable': {'thread_id': thread_id}}
    state = chatBot.get_state(config=CONFIG)

    # Check if state has messages
    if state.values and 'messages' in state.values:
        return state.values['messages']
    return [] # Return empty list

# Generate name for conversation
def generate_conversation_name(messages, thread_id):
    #Generate a name for the conversation based on message history
    # Use a separate thread ID for naming
    naming_thread_id = f"{thread_id}_naming"
    CONFIG = {'configurable': {'thread_id': naming_thread_id}}
    
    # Only use first 6 messages for context (3 exchanges)
    formatted_chat = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in messages[:6]
    )

    response = chatBot.invoke(
        {'messages': [HumanMessage(
            content=f"""
            Generate a short title (max 5 words) for this conversation.
            Do not use punctuation.
            Return only the title.
            Conversation:
            {formatted_chat}
            """)
            ]
        },
        config=CONFIG
    )

    return response['messages'][-1].content.strip()

# ***************************************** Session states *****************************************

# Create a session state to store the messages
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# Thread ID's
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

# List to store thread ids
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

# Add thread
add_thread(st.session_state['thread_id'])


# ******************************************* Sidebar UI ******************************************

st.sidebar.title('Resume ChatBot')

# New Chat
if st.sidebar.button('New Chat'):
    reset_chat()
    st.rerun() # Refresh the page

st.sidebar.header('My Conversations')

# Display all conversations
for thread in st.session_state['chat_threads'][::-1]:
    thread_id = thread['id']
    name = thread['name']

    if st.sidebar.button(name, key=thread_id):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []

        # Check for empty messages
        if messages:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    role = 'user'
                else:
                    role  = 'assistant'
                temp_messages.append({'role': role, 'content': msg.content})

        st.session_state['message_history'] = temp_messages
        st.rerun() # refresh the display



# ******************************************** Main Ui ********************************************

# load all messages
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input('Type here ')

if user_input:
    # store the message 
    st.session_state['message_history'].append({'role':'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    # With streaming
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}
    with st.chat_message('assistant'):

        ai_message = st.write_stream(
            message_chunk.content for message_chunk, metadata in chatBot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages'
            )
        )
    st.session_state['message_history'].append({'role':'assistant', 'content': ai_message})


    # Rename only after new message
    # Get current thread
    current_thread = None
    for thread in st.session_state['chat_threads']:
        if thread['id'] == st.session_state['thread_id']:
            current_thread = thread
            break
    
    # Only generate name if:
    #  - Thread hasn't been named yet (prevents re-naming)
    #  - There are at least 3 messages (enough context for meaningful name)
    if current_thread and not current_thread.get('named', False) and len(st.session_state['message_history']) >= 3:
        try:
            name = generate_conversation_name(
                st.session_state['message_history'], 
                st.session_state['thread_id']
            )
            current_thread['name'] = name
            current_thread['named'] = True  # Mark as named
        except Exception as e:
            print(f"Error generating name: {e}")
            # Keep the default name if naming fails
    
    st.rerun()  # Rerun to update the sidebar with new message/name




