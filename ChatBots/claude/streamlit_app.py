import streamlit as st
from backend_with_tools import chatBot
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlite_db import save_thread_metadata
from rag_utility import ingest_pdf, load_existing_retriever, get_thread_metadata, _get_retriever
from utility_tools import execute_rag_query

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
    
    # FIXED: Only load HumanMessage and AIMessage, skip ToolMessage and empty/tool-only AIMessages
    if messages:
        for msg in messages:
            # Skip tool messages completely
            if isinstance(msg, ToolMessage):
                continue
            
            if isinstance(msg, HumanMessage):
                role = 'user'
                content = msg.content
            elif isinstance(msg, AIMessage):
                # Skip AIMessages that are just tool calls (no actual text content)
                # These are the intermediate messages where AI decides to use a tool
                if hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content:
                    continue
                
                role = 'assistant'
                content = msg.content
                
                # Skip AIMessages with no content or only whitespace
                if not content or content.strip() == "":
                    continue
            else:
                # Skip any other message types
                continue
            
            # Only add if there's actual content
            if content and content.strip():
                temp_messages.append({'role': role, 'content': content})
    
    st.session_state['message_history'] = temp_messages

# PDF upload state
if 'pdf_uploaded' not in st.session_state:
    st.session_state['pdf_uploaded'] = False


# ******************************************* Sidebar UI ******************************************

st.sidebar.title('Multi Utility ChatBot')

# New Chat
if st.sidebar.button('New Chat'):
    reset_chat()
    st.session_state['pdf_uploaded'] = False
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

        # FIXED: Only load HumanMessage and AIMessage, skip ToolMessage and empty/tool-only AIMessages
        if messages:
            for msg in messages:
                # Skip tool messages completely
                if isinstance(msg, ToolMessage):
                    continue
                
                if isinstance(msg, HumanMessage):
                    role = 'user'
                    content = msg.content
                elif isinstance(msg, AIMessage):
                    # Skip AIMessages that are just tool calls (no actual text content)
                    # These are the intermediate messages where AI decides to use a tool
                    if hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content:
                        continue
                    
                    role = 'assistant'
                    content = msg.content
                    
                    # Skip AIMessages with no content or only whitespace
                    if not content or content.strip() == "":
                        continue
                else:
                    # Skip any other message types
                    continue
                
                # Only add if there's actual content
                if content and content.strip():
                    temp_messages.append({'role': role, 'content': content})
        
        st.session_state['message_history'] = temp_messages
        
        # Try to load existing PDF for this thread
        retriever = load_existing_retriever(thread_id)
        st.session_state['pdf_uploaded'] = retriever is not None
        
        st.rerun()

# PDF Upload Section
st.sidebar.header('📄 Document Upload')

# Check if current thread has a PDF
current_pdf_meta = get_thread_metadata(st.session_state['thread_id'])
if current_pdf_meta:
    st.sidebar.success(f"✅ Loaded: {current_pdf_meta.get('filename', 'Document')}")
    st.sidebar.caption(f"Pages: {current_pdf_meta.get('documents', 'N/A')} | Chunks: {current_pdf_meta.get('chunks', 'N/A')}")
elif st.session_state.get('pdf_uploaded', False):
    st.sidebar.info("Document loaded for this conversation")
else:
    st.sidebar.info("No document uploaded yet")

uploaded_file = st.sidebar.file_uploader("Upload PDF/Resume", type=['pdf'], key='pdf_uploader')

if uploaded_file:
    if not st.session_state.get('pdf_uploaded', False):
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
                st.write("✅ Document processed successfully!")
                status.update(label="✅ Document ready!", state="complete")
                st.session_state['pdf_uploaded'] = True
                st.rerun()
            else:
                st.error(f"Error: {result.get('message', 'Unknown error')}")
                status.update(label="❌ Processing failed", state="error")


# ******************************************** Main UI ********************************************

st.title("🤖 Multi-Utility Chatbot")

# Show PDF status in main area
if _get_retriever(st.session_state['thread_id']):
    pdf_meta = get_thread_metadata(st.session_state['thread_id'])
    if pdf_meta:
        st.info(f"💡 You can ask questions about: **{pdf_meta.get('filename', 'your document')}**")

# Load all messages - tool messages already filtered out in message_history
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
        "metadata": {"thread_id": st.session_state["thread_id"]},
        "run_name": "chat_turn"
    }

    with st.chat_message('assistant'):
        # Mutable holder for status container and response
        status_holder = {"box": None}
        response_parts = []  # Use list instead of string to avoid nonlocal issues
        
        def ai_stream_with_rag():
            """Stream AI response, show tool status but don't display tool outputs"""
            
            for message_chunk, metadata in chatBot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages'
            ):
                # Handle tool messages - SHOW STATUS BUT DON'T STREAM CONTENT
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    
                    # Special handling for RAG tool
                    if tool_name == "rag_tool":
                        if status_holder["box"] is None:
                            status_holder["box"] = st.status(
                                f"🔍 Searching document...",
                                expanded=True
                            )
                        else:
                            status_holder["box"].update(
                                label=f"🔍 Searching document...",
                                state="running",
                                expanded=True,
                            )
                    else:
                        # Other tools
                        if status_holder["box"] is None:
                            status_holder["box"] = st.status(
                                f"🔧 Using `{tool_name}`...",
                                expanded=True
                            )
                        else:
                            status_holder["box"].update(
                                label=f"🔧 Using `{tool_name}`...",
                                state="running",
                                expanded=True,
                            )
                    
                    # DON'T yield tool content - just continue
                    continue

                # Stream only assistant content
                if isinstance(message_chunk, AIMessage):
                    # Check if this is a tool call decision
                    if hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls:
                        for tool_call in message_chunk.tool_calls:
                            tool_name = tool_call.get('name', 'unknown')
                            
                            # Special RAG handling
                            if tool_name == 'rag_tool':
                                query = tool_call.get('args', {}).get('query', user_input)
                                
                                # Execute RAG manually
                                rag_result = execute_rag_query(
                                    query=query,
                                    thread_id=st.session_state['thread_id']
                                )
                                
                                # Show results in status
                                if status_holder["box"]:
                                    if 'error' in rag_result:
                                        status_holder["box"].write(f"⚠️ {rag_result['error']}")
                                    else:
                                        status_holder["box"].write(f"✅ Found {rag_result.get('num_chunks', 0)} relevant sections")
                    
                    # Yield content for streaming
                    if message_chunk.content:
                        response_parts.append(message_chunk.content)
                        yield message_chunk.content

        # Stream the response
        ai_message = st.write_stream(ai_stream_with_rag())

        # Finalize status
        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Complete", state="complete", expanded=False
            )

    # Store the final message - join response_parts or use ai_message as fallback
    final_message = "".join(response_parts) if response_parts else ai_message
    
    if final_message:
        st.session_state['message_history'].append({'role': 'assistant', 'content': final_message})
    
    # Get current thread
    current_thread = None
    for thread in st.session_state['chat_threads']:
        if thread['id'] == st.session_state['thread_id']:
            current_thread = thread
            break
    
    # Generate name if needed
    if current_thread and not current_thread.get('named', False) and len(st.session_state['message_history']) >= 3:
        try:
            name = generate_conversation_name(
                st.session_state['message_history'], 
                st.session_state['thread_id']
            )
            current_thread['name'] = name
            current_thread['named'] = True
            
            save_thread_metadata(st.session_state['thread_id'], name, True)
            
        except Exception as e:
            print(f"Error generating name: {e}")
    
    st.rerun()