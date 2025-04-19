import streamlit as st
from graph_workflow import vibe_coding_assistant, architecture_assistant
import graphviz
import logging
import base64

from datetime import datetime
st.title("Vibe Coding Assistant")

def create_detailed_graph_visualization() -> graphviz.Digraph:
    """Create a visualization of the LangGraph workflow"""
    dot = graphviz.Digraph(comment='LangGraph Workflow')
    dot.attr(rankdir='LR')
    
    # Style definitions
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
    dot.attr('edge', fontsize='10')
    
    # Add nodes
    dot.node("START", "START", shape='circle', fillcolor='lightgreen')
    dot.node("parse_requirements", "Parse Requirements")
    dot.node("generate_code", "Generate Code")
    dot.node("explain_code", "Explain Code")
    dot.node("END", "END", shape='doublecircle', fillcolor='lightpink')
    
    # Add edges with descriptions
    dot.edge("START", "parse_requirements", "Begin")
    dot.edge("parse_requirements", "generate_code", "Analysis Complete")
    dot.edge("generate_code", "explain_code", "Code Generated")
    dot.edge("explain_code", "END", "Complete")
    
    return dot

def save_diagram(dot: graphviz.Digraph, name: str, formats=['pdf', 'png', 'svg']) -> dict:
    """
    Save diagram in multiple formats and return their paths
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{name}_{timestamp}"
    output_dir = "generated_diagrams"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = {}
    for fmt in formats:
        try:
            filename = f"{base_filename}.{fmt}"
            filepath = os.path.join(output_dir, filename)
            dot.render(filepath, format=fmt, cleanup=True)
            saved_files[fmt] = filepath
        except Exception as e:
            st.error(f"Failed to save {fmt} format: {str(e)}")
    
    return saved_files

def get_download_link(file_path: str, format: str) -> str:
    """
    Generate a download link for a file
    """
    try:
        with open(file_path, "rb") as file:
            contents = file.read()
        b64 = base64.b64encode(contents).decode()
        filename = os.path.basename(file_path)
        return f'<a href="data:application/{format};base64,{b64}" download="{filename}">Download {format.upper()}</a>'
    except Exception as e:
        return f"Error generating download link: {str(e)}"


# Update your Streamlit interface
st.title("Vibe Coding Assistant")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["Code Generation", "Architecture Diagram", "Workflow Visualization"])

# ... (keep existing tab1 and tab2 code)

with tab3:
    st.subheader("LangGraph Workflow")
    workflow_dot = create_detailed_graph_visualization()
    st.graphviz_chart(workflow_dot)
    
    st.markdown("""
    ### Workflow Steps
    1. **Start**: Workflow initialization
    2. **Parse Requirements**: Analyzes user input and breaks down requirements
    3. **Generate Code**: Creates implementation based on analysis
    4. **Explain Code**: Provides detailed explanation of generated code
    5. **End**: Workflow completion
    
    ### Process Flow
    - Each step processes the input and updates the state
    - State transitions are managed by the workflow router
    - Results are accumulated through the process
    """)

    # Add download capability for workflow diagram
    if st.button("Download Workflow Diagram"):
        try:
            saved_files = save_diagram(workflow_dot, "langgraph_workflow", formats=['png', 'pdf', 'svg'])
            
            st.subheader("Download Workflow Diagram")
            cols = st.columns(len(saved_files))
            for i, (fmt, filepath) in enumerate(saved_files.items()):
                with cols[i]:
                    st.markdown(
                        get_download_link(filepath, fmt),
                        unsafe_allow_html=True
                    )
        except Exception as e:
            st.error(f"Failed to save workflow diagram: {str(e)}")

# # Create tabs for different functionalities
# tab1, tab2 = st.tabs(["Code Generation", "Architecture Diagram"])

with tab1:
    code_input = st.text_area("Describe what you want to build:", height=200, key="code_input")
    
    if st.button("Generate Code"):
        if code_input:
            initial_state = {
                "user_requirements": code_input,
                "current_step": "parse_requirements",
                "requirements_analysis": None,
                "generated_code": None,
                "explanations": None
            }

            with st.spinner("Processing your request..."):
                try:
                    result = vibe_coding_assistant.invoke(initial_state)

                    if "requirements_analysis" in result:
                        st.subheader("Requirements Analysis")
                        st.write(result["requirements_analysis"])

                    if "generated_code" in result:
                        st.subheader("Generated Code")
                        st.code(result["generated_code"])

                    if "explanations" in result:
                        st.subheader("Code Explanation")
                        st.write(result["explanations"])
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter your requirements first.")

with tab2:
    arch_input = st.text_area("Describe the system architecture:", height=200, key="arch_input",
                             placeholder="Example: Create a web application with a React frontend, Python backend API, and PostgreSQL database...")
    
    if st.button("Generate Architecture Diagram"):
        if arch_input:
            initial_state = {
                "user_requirements": arch_input,
                "current_step": "parse_architecture",
                "architecture_components": None,
                "diagram_code": None
            }

            with st.spinner("Generating architecture diagram..."):
                try:
                    result = architecture_assistant.invoke(initial_state)
                    
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        if "architecture_components" in result:
                            st.subheader("Architecture Components")
                            st.json(result["architecture_components"])
                        
                        if "diagram_code" in result:
                            st.subheader("Architecture Diagram")
                            try:
                                dot = graphviz.Source(result["diagram_code"])
                                st.graphviz_chart(dot)
                            except Exception as e:
                                st.error(f"Failed to render diagram: {str(e)}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter your architecture requirements first.")

# Add sidebar with component information
st.sidebar.markdown("""
### Component Types
- 🟦 Service: Application services and APIs
- 🟧 Database: Data storage systems
- 🟩 Storage: File storage systems
- 🟥 Compute: Processing units
- 🟪 Network: Network components
- ⬜ Client: User-facing components

### How to Use
1. Choose the tab for your desired functionality
2. Enter your requirements
3. Click the generate button
4. View the results
""")




# # Update your Streamlit app to use the detailed visualization:
# st.title("Vibe Coding Assistant")

# # Create two columns
# col1, col2 = st.columns([2, 1])

# with col1:
#     user_input = st.text_area("Describe what you want to build:", height=200)
    
#     if st.button("Generate Code"):
#         if user_input:
#             initial_state = {
#                 "user_requirements": user_input,
#                 "current_step": "parse_requirements",
#                 "requirements_analysis": None,
#                 "generated_code": None,
#                 "explanations": None
#             }

#             with st.spinner("Processing your request..."):
#                 result = vibe_coding_assistant.invoke(initial_state)

#                 if "requirements_analysis" in result:
#                     st.subheader("Requirements Analysis")
#                     st.write(result["requirements_analysis"])

#                 if "generated_code" in result:
#                     st.subheader("Generated Code")
#                     st.code(result["generated_code"])

#                 if "explanations" in result:
#                     st.subheader("Code Explanation")
#                     st.write(result["explanations"])
#         else:
#             st.error("Please enter your requirements first.")

# # Show graph visualization in the second column
# with col2:
#     st.subheader("Workflow Graph")
#     detailed_dot = create_detailed_graph_visualization()
#     st.graphviz_chart(detailed_dot)
    
#     st.markdown("""
#     ### Graph Legend
#     - **START**: Entry point
#     - **Parse Requirements**: Analyzes user input
#     - **Generate Code**: Creates code implementation
#     - **Explain Code**: Provides code explanation
#     - **END**: Completion point
#     """)