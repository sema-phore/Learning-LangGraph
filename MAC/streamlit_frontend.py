import streamlit as st
from langgraph_backend import chatBot
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlite_functions import save_thread_metadata
from rag_utility import ingest_pdf, load_existing_retriever, get_thread_metadata as get_pdf_metadata, _get_retriever
from utility_tools import set_rag_thread_id


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
    # Load Previous Conversations for the current thread
    messages = load_conversation(st.session_state['thread_id'])
    temp_messages = []
    
    # Check for HumanMessage or AIMessage
    if messages:
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = 'user'
            elif isinstance(msg, AIMessage):
                role = 'assistant'
            else:
                continue  # Skip ToolMessage
            temp_messages.append({'role': role, 'content': msg.content})
    
    st.session_state['message_history'] = temp_messages

# Try to load existing PDF for current thread
if 'pdf_loaded' not in st.session_state:
    st.session_state['pdf_loaded'] = False

# Load existing retriever if available
retriever = load_existing_retriever(st.session_state['thread_id'])
if retriever:
    st.session_state['pdf_loaded'] = True


# ******************************************* Sidebar UI ******************************************

st.sidebar.title('Multi Utility ChatBot')

# New Chat
if st.sidebar.button('New Chat'):
    reset_chat()
    st.session_state['pdf_loaded'] = False
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
                if isinstance(msg, ToolMessage):
                    continue
                if isinstance(msg, HumanMessage):
                    role = 'user'
                elif isinstance(msg, AIMessage):
                    role = 'assistant'
                else:
                    continue
                temp_messages.append({'role': role, 'content': msg.content})
        
        st.session_state['message_history'] = temp_messages
        
        # Try to load existing PDF for this thread
        retriever = load_existing_retriever(thread_id)
        st.session_state['pdf_loaded'] = retriever is not None
        
        st.rerun()


# ****************************************** PDF Upload Section ******************************************

st.sidebar.markdown("---")
st.sidebar.header('📄 Document Upload')

# Check if current thread has a PDF
current_pdf_meta = get_pdf_metadata(st.session_state['thread_id'])
if current_pdf_meta:
    st.sidebar.success(f"✅ {current_pdf_meta.get('filename', 'Document')}")
    st.sidebar.caption(f"📄 {current_pdf_meta.get('documents', 'N/A')} pages | ✂️ {current_pdf_meta.get('chunks', 'N/A')} chunks")
else:
    st.sidebar.info("No document uploaded for this chat")

uploaded_file = st.sidebar.file_uploader("Upload PDF", type=['pdf'], key='pdf_uploader')

if uploaded_file and not current_pdf_meta:
    with st.sidebar.status("Processing document...", expanded=True) as status:
        st.write("📖 Reading PDF...")
        file_bytes = uploaded_file.read()
        
        st.write("✂️ Splitting into chunks...")
        result = ingest_pdf(
            file_bytes=file_bytes,
            thread_id=st.session_state['thread_id'],
            filename=uploaded_file.name
        )
        
        if result.get('success', False):
            st.write("✅ Processing complete!")
            status.update(label="✅ Document ready!", state="complete")
            st.session_state['pdf_loaded'] = True
            st.rerun()
        else:
            st.error(f"❌ {result.get('message', 'Unknown error')}")
            status.update(label="❌ Failed", state="error")


# ******************************************** Main UI ********************************************

st.title("🤖 Multi-Utility Chatbot")

# Show PDF status banner if document is loaded
if _get_retriever(st.session_state['thread_id']):
    pdf_meta = get_pdf_metadata(st.session_state['thread_id'])
    if pdf_meta:
        st.info(f"💡 **Document loaded:** {pdf_meta.get('filename', 'your document')} - You can ask questions about it!")

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

    # Set thread_id for RAG tool before invoking chatbot
    set_rag_thread_id(st.session_state['thread_id'])

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
                    
                    # Special display for RAG tool
                    if tool_name == "rag_tool":
                        label = "🔍 Searching document..."
                    else:
                        label = f"🔧 Using `{tool_name}` …"
                    
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(label, expanded=True)
                    else:
                        status_holder["box"].update(
                            label=label,
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
