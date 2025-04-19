# import json
# import boto3
# from typing import TypedDict, Dict
# from langgraph.graph import StateGraph, END
# import logging
# from datetime import datetime
# import graphviz

# MODEL_ID="anthropic.claude-3-sonnet-20240229-v1:0" # "anthropic.claude-3-haiku-20240307-v1:0", 
# # Set up logging
# logging.basicConfig(level=logging.INFO,
#                    format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# # Bedrock client setup
# bedrock_runtime = boto3.client(
#     service_name='bedrock-runtime',
#     region_name='us-east-1'  # Replace with your region
# )

# class VibeCodingState(TypedDict):
#     user_requirements: str
#     current_step: str
#     requirements_analysis: str | None
#     generated_code: str | None
#     explanations: str | None
#     architecture_components: Dict | None
#     diagram_code: str | None

# def generate_architecture_diagram(components: Dict) -> graphviz.Digraph:
#     """Generate architecture diagram using Graphviz"""
#     dot = graphviz.Digraph(comment='Architecture Diagram')
#     dot.attr(rankdir='LR')
    
#     # Define styles for different component types
#     styles = {
#         'service': {'shape': 'rectangle', 'style': 'rounded', 'color': 'blue'},
#         'database': {'shape': 'cylinder', 'color': 'orange'},
#         'storage': {'shape': 'folder', 'color': 'green'},
#         'compute': {'shape': 'box3d', 'color': 'red'},
#         'network': {'shape': 'diamond', 'color': 'purple'},
#         'client': {'shape': 'component', 'color': 'gray'}
#     }
    
#     # Add nodes
#     for name, details in components['nodes'].items():
#         node_style = styles.get(details['type'], {})
#         dot.node(name, f"{name}\n{details.get('description', '')}", **node_style)
    
#     # Add edges
#     for edge in components['edges']:
#         dot.edge(edge['from'], edge['to'], edge.get('label', ''))
    
#     return dot

# def parse_architecture(state: VibeCodingState) -> Dict:
#     """Parse requirements and generate architecture components"""
#     logger.info("Starting architecture analysis")
    
#     prompt = f"""
#     As a solutions architect, analyze these requirements and provide a detailed architecture design:

#     Requirements:
#     {state['user_requirements']}

#     Provide the architecture components in the following JSON format:
#     {{
#         "nodes": {{
#             "component_name": {{"type": "service|database|storage|compute|network|client", "description": "description"}}
#         }},
#         "edges": [
#             {{"from": "component_name", "to": "component_name", "label": "interaction description"}}
#         ]
#     }}

#     Return only the JSON without any additional text.
#     """
    
#     logger.info("Requesting architecture components from Claude")
#     components_json = invoke_claude(prompt)
    
#     try:
#         components = json.loads(components_json)
#         logger.info("Successfully parsed architecture components")
#         return {
#             "current_step": "generate_diagram",
#             "architecture_components": components
#         }
#     except json.JSONDecodeError as e:
#         logger.error(f"Failed to parse architecture JSON: {e}")
#         return {
#             "current_step": "end",
#             "error": f"Failed to parse architecture: {str(e)}"
#         }

# def generate_diagram(state: VibeCodingState) -> Dict:
#     """Generate diagram from architecture components"""
#     logger.info("Generating architecture diagram")
    
#     try:
#         components = state.get('architecture_components', {})
#         if not components:
#             raise ValueError("No architecture components found")
            
#         dot = generate_architecture_diagram(components)
#         diagram_code = dot.source
        
#         logger.info("Successfully generated diagram")
#         return {
#             "current_step": "end",
#             "diagram_code": diagram_code
#         }
#     except Exception as e:
#         logger.error(f"Failed to generate diagram: {e}")
#         return {
#             "current_step": "end",
#             "error": f"Failed to generate diagram: {str(e)}"
#         }

# def invoke_claude(prompt: str, max_tokens: int = 2000, temperature: float = 0.5) -> str:
#     try:
#         logger.info(f"Invoking Claude with prompt length: {len(prompt)} characters")
#         request_id = datetime.now().strftime("%Y%m%d-%H%M%S")
#         logger.info(f"Request ID: {request_id}")
#         body = json.dumps({
#             "anthropic_version": "bedrock-2023-05-31",
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ],
#             "max_tokens": max_tokens,
#             "temperature": temperature
#         })
        
#         response = bedrock_runtime.invoke_model(
#             modelId=MODEL_ID,
#             contentType="application/json",
#             body=body
#         )
        
#         response_body = json.loads(response.get('body').read())
#         return response_body.get('content')[0].get('text', '').strip()
#     except Exception as e:
#         print(f"Error invoking Claude: {str(e)}")
#         return f"Error generating response: {str(e)}"

# def parse_requirements(state: VibeCodingState) -> Dict:
#     logger.info("Starting requirements parsing phase")
#     logger.info(f"Input requirements length: {len(state['user_requirements'])} characters")

#     prompt = f"""
#     You are a senior software engineer. Analyze these user requirements and break them down into clear technical specifications:

#     User Requirements:
#     {state['user_requirements']}

#     Provide a detailed analysis including:
#     1. Main components/features needed
#     2. Technical approach
#     3. Any potential challenges
#     4. Required libraries/dependencies
#     """
#     logger.info("Sending requirements analysis prompt to Claude")

#     analysis = invoke_claude(prompt)
#     logger.info("Requirements analysis completed")
#     return {
#         "current_step": "generate_code",
#         "requirements_analysis": analysis
#     }
    
# def generate_code(state: VibeCodingState) -> Dict:
#     logger.info("Starting code generation phase")
#     logger.info(f"Using analysis of length: {len(state.get('requirements_analysis', ''))} characters")

#     prompt = f"""
#     You are a senior software engineer. Generate production-quality code based on these requirements and analysis:

#     User Requirements:
#     {state['user_requirements']}

#     Technical Analysis:
#     {state.get('requirements_analysis', '')}

#     Please provide:
#     1. Complete, working code implementation
#     2. Include necessary imports
#     3. Add clear comments explaining key parts
#     4. Follow best practices and proper error handling
#     5. Make the code modular and maintainable

#     Return only the code without any additional explanations.
#     """
#     logger.info("Sending code generation prompt to Claude")
#     generated_code = invoke_claude(prompt)
#     logger.info(f"Code generation completed. Generated code length: {len(generated_code)} characters")

#     return {
#         "current_step": "explain_code",
#         "generated_code": generated_code
#     }

# def explain_code(state: VibeCodingState) -> Dict:
#     logger.info("Starting code explanation phase")
#     logger.info(f"Code to explain length: {len(state.get('generated_code', ''))} characters")

#     prompt = f"""
#     You are a senior software engineer. Provide a detailed explanation of this code:

#     {state.get('generated_code', '')}

#     Please explain:
#     1. Overall architecture and design choices
#     2. How each component works
#     3. Best practices used
#     4. Any important implementation details
#     5. How to use the code
#     """
#     logger.info("Sending code explanation prompt to Claude")
#     explanation = invoke_claude(prompt)
#     logger.info("Code explanation completed")
#     return {
#         "current_step": "end",
#         "explanations": explanation
#     }

# def should_continue(state: VibeCodingState) -> str:
#     """Determine the next step in the workflow"""
#     return state["current_step"]

# # Define the conditional edge function
# def next_step(state: VibeCodingState) -> str:
#     return state["current_step"]

# def router(state: VibeCodingState) -> str:
#     """Route to the next step based on current_step"""
#     return state["current_step"]

# # Create the workflows
# code_workflow = StateGraph(VibeCodingState)
# architecture_workflow = StateGraph(VibeCodingState)

# # Add nodes for code workflow
# code_workflow.add_node("parse_requirements", parse_requirements)
# code_workflow.add_node("generate_code", generate_code)
# code_workflow.add_node("explain_code", explain_code)

# # Add nodes for architecture workflow
# architecture_workflow.add_node("parse_architecture", parse_architecture)
# architecture_workflow.add_node("generate_diagram", generate_diagram)

# # Set entry points
# code_workflow.set_entry_point("parse_requirements")
# architecture_workflow.set_entry_point("parse_architecture")

# # Add conditional edges for code workflow
# code_workflow.add_conditional_edges(
#     "parse_requirements",
#     router,
#     {
#         "generate_code": "generate_code",
#         "end": END
#     }
# )

# code_workflow.add_conditional_edges(
#     "generate_code",
#     router,
#     {
#         "explain_code": "explain_code",
#         "end": END
#     }
# )

# code_workflow.add_conditional_edges(
#     "explain_code",
#     router,
#     {
#         "end": END
#     }
# )

# # Add conditional edges for architecture workflow
# architecture_workflow.add_conditional_edges(
#     "parse_architecture",
#     router,
#     {
#         "generate_diagram": "generate_diagram",
#         "end": END
#     }
# )

# architecture_workflow.add_conditional_edges(
#     "generate_diagram",
#     router,
#     {
#         "end": END
#     }
# )

# # Compile the workflows
# logger.info("Compiling workflow")
# vibe_coding_assistant = code_workflow.compile()
# architecture_assistant = architecture_workflow.compile()
# # Compile the workflow
# logger.info("Workflow compilation completed")