import streamlit as st
from graph_workflow import multi_agent_assistant, create_workflow_diagram, ConversationEntry , ConversationStore
import graphviz
import json
from datetime import datetime
from typing import List, Dict

st.title("Multi-Agent Software Development Assistant")

# Initialize conversation store
conversation_store = ConversationStore()

def load_conversation_history():
    """Load conversation history from storage"""
    return conversation_store.load_history()

def save_conversation_history(history: List[Dict]):
    """Save conversation history to storage"""
    conversation_store.save_history(history)

def display_conversation_history(history: List[Dict]):
    """Display conversation history in Streamlit"""
    st.subheader("Conversation History")
    
    # Add clear history button
    if st.button("Clear History"):
        save_conversation_history([])
        st.session_state.conversation_history = []
        st.experimental_rerun()
    
    for i, entry in enumerate(reversed(history)):  # Show newest first
        with st.expander(f"Question {len(history)-i} - {entry['timestamp']}", expanded=False):
            st.write("**Question:**")
            st.write(entry['question'])
            
            if entry.get('architecture_diagram'):
                st.write("**Architecture Diagram:**")
                try:
                    dot = graphviz.Source(entry['architecture_diagram'])
                    st.graphviz_chart(dot)
                except Exception as e:
                    st.error(f"Failed to render diagram: {str(e)}")
            
            if entry.get('code'):
                st.write("**Generated Code:**")
                st.code(entry['code'])
            
            if entry.get('explanation'):
                st.write("**Explanation:**")
                st.write(entry['explanation'])
                
                
def display_conversation_history(history: list):
    """Display conversation history in Streamlit"""
    st.subheader("Conversation History")
    
    for i, entry in enumerate(history):
        with st.expander(f"Question {i+1} - {entry['timestamp']}", expanded=False):
            st.write("**Question:**")
            st.write(entry['question'])
            
            if entry.get('architecture_diagram'):
                st.write("**Architecture Diagram:**")
                try:
                    dot = graphviz.Source(entry['architecture_diagram'])
                    st.graphviz_chart(dot)
                except Exception as e:
                    st.error(f"Failed to render diagram: {str(e)}")
            
            if entry.get('code'):
                st.write("**Generated Code:**")
                st.code(entry['code'])
            
            if entry.get('explanation'):
                st.write("**Explanation:**")
                st.write(entry['explanation'])

def display_results(final_output: dict):
    """Display the results in an organized manner"""
    tabs = st.tabs(["Requirements", "Architecture", "Implementation"])
    
    with tabs[0]:
        if "requirements_analysis" in final_output:
            st.write(final_output["requirements_analysis"])
    
    with tabs[1]:
        if "architecture" in final_output:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("Components")
                st.json(final_output["architecture"]["components"])
            
            with col2:
                st.subheader("Architecture Diagram")
                diagram_code = final_output["architecture"].get("diagram")
                if diagram_code and isinstance(diagram_code, str):
                    try:
                        dot = graphviz.Source(diagram_code)
                        st.graphviz_chart(dot)
                    except Exception as e:
                        st.error(f"Failed to render diagram: {str(e)}")
    
    with tabs[2]:
        if "implementation" in final_output:
            st.subheader("Generated Code")
            if final_output["implementation"].get("code"):
                st.code(final_output["implementation"]["code"])
            
            st.subheader("Code Explanation")
            if final_output["implementation"].get("explanation"):
                st.write(final_output["implementation"]["explanation"])


def main():    
     # Initialize session state for conversation history
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = load_conversation_history()
        
    # Create tabs for different views
    main_tab, history_tab, workflow_tab = st.tabs([
        "Main Interface",
        "Conversation History",
        "Workflow Diagram"
    ])
    
    with main_tab:
        user_input = st.text_area(
            "Describe what you want to build:",
            height=200,
            placeholder="Describe your software requirements in detail..."
        )
        
        if st.button("Generate Solution"):
            if user_input:
                # Create new conversation entry
                entry = ConversationEntry(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    question=user_input
                )
                
                initial_state = {
                    "user_requirements": user_input,
                    "current_agent": "supervisor",
                    "tasks_completed": [],
                    "architecture_components": None,
                    "diagram_code": None,
                    "requirements_analysis": None,
                    "generated_code": None,
                    "code_explanation": None,
                    "final_output": None,
                    "error": None,
                    "conversation_history": st.session_state.conversation_history
                }
                
                with st.spinner("Processing your request..."):
                    try:
                        result = multi_agent_assistant.invoke(initial_state)
                        st.session_state.result = result
                        
                        if result.get("error"):
                            st.error(result["error"])
                        else:
                            final_output = result.get("final_output", {})
                                                      # Update conversation entry with results
                            if "architecture" in final_output:
                                entry["architecture_diagram"] = final_output["architecture"].get("diagram")
                            
                            if "implementation" in final_output:
                                entry["code"] = final_output["implementation"].get("code")
                                entry["explanation"] = final_output["implementation"].get("explanation")
                            
                            # Update conversation history
                            st.session_state.conversation_history.append(entry)
                            save_conversation_history(st.session_state.conversation_history)
                            display_results(final_output)
                            
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
            else:
                st.error("Please enter your requirements first.")
    
    with history_tab:
        display_conversation_history(st.session_state.conversation_history)
        # if 'result' in st.session_state and st.session_state.result:
        #     history = st.session_state.result.get('conversation_history', [])
        #     display_conversation_history(history)
        # else:
        #     st.info("No conversation history yet.")
    
    with workflow_tab:
        st.subheader("Workflow Diagram")
        workflow_dot = create_workflow_diagram()
        st.graphviz_chart(workflow_dot)
        
        st.markdown("""
        ### Workflow Steps
        1. **Supervisor Agent**: Orchestrates the entire workflow
        2. **Requirements Analyzer**: Breaks down user requirements
        3. **Architecture Designer**: Creates system architecture
        4. **Code Generator**: Implements the solution
        5. **Code Explainer**: Documents the implementation
        6. **Output Consolidator**: Combines all outputs
        
        ### Agent Interactions
        - Each agent reports back to the supervisor
        - Supervisor determines the next step
        - Results are accumulated throughout the process
        """)

if __name__ == "__main__":
    main()