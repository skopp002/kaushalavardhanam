import json
import boto3
from typing import TypedDict, Dict, List, Optional
from langgraph.graph import StateGraph, END
import logging
from datetime import datetime
import graphviz
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import base64
from botocore.exceptions import ClientError 
import pdb

MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"#"amazon.nova-pro-v1:0" #"anthropic.claude-3-sonnet-20240229-v1:0"
TRUNCATE_TOKENS = 1000
# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s()-%(message)s')
logger = logging.getLogger(__name__)

# Bedrock client setup
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1'
)

bedrock_agent_runtime = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name='us-east-1'
)

class ConversationStore:
    def __init__(self, storage_path: str = "conversation_history.json"):
        self.storage_path = storage_path
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Create storage file if it doesn't exist"""
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, 'w') as f:
                json.dump([], f)
    
    def load_history(self) -> List[Dict]:
        """Load conversation history from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return []
    
    def save_history(self, history: List[Dict]):
        """Save conversation history to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")

class ConversationEntry:
    def __init__(self, timestamp: str, question: str, 
                 architecture_diagram: Optional[str] = None,
                 code: Optional[str] = None, 
                 explanation: Optional[str] = None):
        self.timestamp = timestamp
        self.question = question
        self.architecture_diagram = architecture_diagram
        self.code = code
        self.explanation = explanation
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'question': self.question,
            'architecture_diagram': self.architecture_diagram,
            'code': self.code,
            'explanation': self.explanation
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            timestamp=data.get('timestamp'),
            question=data.get('question'),
            architecture_diagram=data.get('architecture_diagram'),
            code=data.get('code'),
            explanation=data.get('explanation')
        )

class WorkflowState(TypedDict):
    user_requirements: str
    current_agent: str
    tasks_completed: List[str]
    architecture_components: Dict | None
    diagram_code: str | None
    requirements_analysis: str | None
    generated_code: str | None
    code_explanation: str | None
    final_output: Dict | None
    error: str | None
    conversation_history: List[ConversationEntry]


class InlineAgentActions:
    """Define common action groups for inline agents"""
    
    @staticmethod
    def get_architecture_actions() -> List[Dict]:
        return [{
            "actionGroupName": "ArchitectureActions",
            "actionGroupExecutor": "AWS_LAMBDA",
            "apiSchema": {
                "openapi": "3.0.0",
                "info": {
                    "title": "Architecture Design API",
                    "version": "1.0.0"
                },
                "paths": {
                    "/generate-architecture": {
                        "post": {
                            "operationId": "GenerateArchitecture",
                            "summary": "Generate AWS architecture diagram",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "requirements": {
                                                    "type": "string",
                                                    "description": "User requirements"
                                                },
                                                "services": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string"
                                                    },
                                                    "description": "AWS services to include"
                                                }
                                            },
                                            "required": ["requirements"]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }]
    
    @staticmethod
    def get_code_actions() -> List[Dict]:
        return [{
            "actionGroupName": "CodeActions",
            "actionGroupExecutor": "AWS_LAMBDA",
            "apiSchema": {
                "openapi": "3.0.0",
                "info": {
                    "title": "Code Generation API",
                    "version": "1.0.0"
                },
                "paths": {
                    "/generate-code": {
                        "post": {
                            "operationId": "GenerateCode",
                            "summary": "Generate implementation code",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "architecture": {
                                                    "type": "object",
                                                    "description": "Architecture components"
                                                },
                                                "language": {
                                                    "type": "string",
                                                    "description": "Programming language"
                                                }
                                            },
                                            "required": ["architecture"]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }]

class InlineAgent:
    def __init__(self, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        self.model_id = model_id
        self.session_id = None
    
    def _format_prompt(self, prompt: str, action_groups: List[Dict] = None) -> str:
        """Format the prompt with action groups"""
        if not action_groups:
            return prompt
        
        formatted_prompt = f"""
        {prompt}

        Available Actions:
        {json.dumps(action_groups, indent=2)}

        Please provide your response in the following JSON format:
        {{
            "reasoning": "Your step-by-step reasoning",
            "action": "The action you want to take",
            "parameters": {{
                // Action-specific parameters
            }},
            "result": {{
                // Your final output
            }}
        }}
        """
        return formatted_prompt

    def invoke(self, prompt: str, max_tokens = 2000, action_groups: List[Dict] = None) -> Dict:
        """
        Invoke the model with prompt and optional action groups
        """
        try:
            if TRUNCATE_TOKENS:
                # Reserve tokens for system message and response
                system_reserve = 500
                response_reserve = 1000
                available_tokens = max_tokens - (system_reserve + response_reserve)

            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt#[:available_tokens]
                    }
                ],
                "anthropic_version": "bedrock-2023-05-31",
                 "max_tokens": 4096,
                "temperature": 0.7
            }
            
            response = bedrock_runtime.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response.get('body').read())
            logger.debug(f"Raw Bedrock response: {json.dumps(response_body, indent=2)}")
            
            # Extract the content from Claude's response
            if 'content' in response_body and len(response_body['content']) > 0:
                text_response = response_body['content'][0].get('text', '')
                logger.debug(f"Extracted text response: {text_response}")
                return text_response
            else:
                raise ValueError("No content in model response")
                
        except ClientError as e:
            logger.error(f"AWS API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error invoking model: {str(e)}")
            raise
            
    
def parse_response(response):
    """
    Parse response and extract components with detailed logging
    """
    logger.debug(f"Raw response type: {type(response)}")
    logger.debug(f"Raw response content: {response[:1000]}...")  # Log first 1000 chars
    
    try:
        # First, clean the response if it's a string
        if isinstance(response, str):
            # Try to find JSON content within the string
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx >= 0 and end_idx >= 0:
                # Extract JSON portion
                json_str = response[start_idx:end_idx + 1]
                logger.debug(f"Extracted JSON string: {json_str[:1000]}...")
                print(f"Extracted JSON string: {json_str[:1000]}...")
                # Clean and format the JSON string
                try:
                    # Replace single quotes with double quotes
                    json_str = json_str.replace("'", '"')
                    
                    # Ensure property names are properly quoted
                    import re
                    json_str = re.sub(r'(\w+)(?=\s*:)', r'"\1"', json_str)
                    
                    # Remove any extra whitespace
                    json_str = json_str.strip()
                    
                    logger.debug(f"Cleaned JSON string: {json_str[:1000]}...")
                    print(f"Cleaned JSON string: {json_str[:1000]}...")
                    try:
                        response_dict = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse cleaned JSON: {e}")
                        logger.error(f"Problematic JSON: {json_str}")
                        return {}
                        
                except Exception as e:
                    logger.error(f"Error cleaning JSON: {e}")
                    return {}
            else:
                logger.warning("No JSON structure found in response")
                return {}
        else:
            response_dict = response
        
        logger.debug(f"Parsed dictionary: {json.dumps(response_dict, indent=2)[:1000]}...")
        
        # Try different possible response structures
        if isinstance(response_dict, dict):
            # Try to get components from 'result' key
            components = response_dict.get('result', {})
            
            # If no 'result' key or empty result, try 'architecture' key
            if not components:
                components = response_dict.get('architecture', {})
            
            # If still no components, use entire response if it has expected structure
            if not components and ('nodes' in response_dict or 'edges' in response_dict):
                components = response_dict
            
            # If components is empty but we have a code response
            if not components and 'code' in response_dict:
                return response_dict
                
            logger.debug(f"Final components: {json.dumps(components, indent=2)[:1000]}...")
            return components
        else:
            logger.warning(f"Response is not a dictionary: {type(response_dict)}")
            return {}
            
    except Exception as e:
        logger.error(f"Error parsing response: {e}", exc_info=True)
        return {}

#With ConversationEntry
# def inline_architect_agent(state: WorkflowState) -> Dict:
#     """
#     Inline agent for architecture design
#     """
#     logger.info("Inline architect agent processing")
    
#     try:
#         agent = InlineAgent()
        
#         # Convert state to dictionary if it's a ConversationEntry
#         if isinstance(state, ConversationEntry):
#             state_dict = state.to_dict()
#         else:
#             state_dict = dict(state)
            
#         prompt = f"""
#         You are an AWS Solutions Architect. Design a detailed architecture for the following requirements:
        
#         Requirements:
#         {state_dict['user_requirements']}
        
#         Provide your response as a valid JSON object with the following structure:
#         {{
#             "nodes": {{
#                 "service_name": {{
#                     "type": "aws_service",
#                     "service": "AWS Service Name",
#                     "description": "Service description",
#                     "config": {{
#                         "key": "value"
#                     }}
#                 }}
#             }},
#             "edges": [
#                 {{
#                     "from": "service_name",
#                     "to": "service_name",
#                     "label": "interaction description"
#                 }}
#             ]
#         }}
        
#         Ensure your response is properly formatted JSON without any additional text or explanations outside the JSON structure.
#         """
        
#         response = agent.invoke(prompt=prompt)
#         logger.debug(f"Agent response: {response}")
        
#         # Parse the response and extract components
#         components = parse_response(response)
        
#         if not components:
#             raise ValueError("No valid architecture components found in response")
        
#         if not isinstance(components, dict):
#             raise ValueError(f"Invalid components type: {type(components)}")
        
#         dot = generate_aws_architecture_diagram(components)
#         # Create new conversation entry
#         entry = ConversationEntry(
#             timestamp=datetime.now().isoformat(),
#             question=state_dict['user_requirements'],
#             architecture_diagram=dot.source
#         )
        
#         return {
#             "architecture_components": components,
#             "diagram_code": dot.source,
#             "current_agent": "supervisor",
#             "tasks_completed": state_dict.get('tasks_completed', []) + ["architect"], #state.get('tasks_completed', []) + ["architect"]
#             "conversation_history": state_dict.get('conversation_history', []) + [entry.to_dict()]
#         }
        
#     except Exception as e:
#         logger.error(f"Inline architect agent error: {str(e)}", exc_info=True)
#         # return {
#         #     "error": f"Architecture generation failed: {str(e)}",
#         #     "current_agent": "supervisor",
#         #     "tasks_completed": state.get('tasks_completed', [])
#         # }

def inline_architect_agent(state: WorkflowState) -> Dict:
    """
    Inline agent for architecture design
    """
    logger.info("Inline architect agent processing")
    
    try:
        agent = InlineAgent()
        
        # Convert state to dictionary directly
        state_dict = state if isinstance(state, dict) else dict(state)
            
        prompt = f"""
        You are an AWS Solutions Architect. Design a detailed architecture for the following requirements:
        
        Requirements:
        {state_dict['user_requirements']}
        
        Provide your response as a valid JSON object with the following structure:
        {{
            "nodes": {{
                "service_name": {{
                    "type": "aws_service",
                    "service": "AWS Service Name",
                    "description": "Service description",
                    "config": {{
                        "key": "value"
                    }}
                }}
            }},
            "edges": [
                {{
                    "from": "service_name",
                    "to": "service_name",
                    "label": "interaction description"
                }}
            ]
        }}
        
        Ensure your response is properly formatted JSON without any additional text or explanations outside the JSON structure.
        """
        
        response = agent.invoke(prompt=prompt)
        logger.debug(f"Agent response: {response}")
        
        # Parse the response and extract components
        components = parse_response(response)
        
        if not components:
            raise ValueError("No valid architecture components found in response")
        
        if not isinstance(components, dict):
            raise ValueError(f"Invalid components type: {type(components)}")
        
        dot = generate_aws_architecture_diagram(components)
        
        return {
            "architecture_components": components,
            "diagram_code": dot.source,
            "current_agent": "supervisor",
            "tasks_completed": state_dict.get('tasks_completed', []) + ["architect"]
        }
        
    except Exception as e:
        logger.error(f"Inline architect agent error: {str(e)}", exc_info=True)
        return {
            "error": f"Architecture generation failed: {str(e)}",
            "current_agent": "supervisor",
            "tasks_completed": state.get('tasks_completed', [])
        }



# def inline_coder_agent(state: WorkflowState) -> Dict:
#     """
#     Inline agent for code generation
#     """
#     logger.info("Inline coder agent processing")
    
#     try:
#         agent = InlineAgent()
#         action_groups = InlineAgentActions.get_code_actions()
        
#         # Convert state if needed
#         if isinstance(state, ConversationEntry):
#             state_dict = state.to_dict()
#         else:
#             state_dict = dict(state)
            
#         logger.debug(f"Converted state to dict: {state_dict}")
#         # Changed from instruction to prompt parameter
#         prompt = f"""
#         As an AWS developer, generate implementation code for the following architecture:
        
#         Requirements:
#         {state_dict['user_requirements']}
        
#         Architecture:
#         {json.dumps(state.get('architecture_components', {}), indent=2)}
        
#         Generate:
#         1. AWS CDK infrastructure code
#         2. Application code
#         3. Deployment scripts
#         4. README with setup instructions
        
#         Ensure the code follows AWS best practices and includes error handling.
#         Use the GenerateCode action to create the implementation.
#         """
        
#         # Changed from instruction to prompt
#         response = agent.invoke(prompt=prompt, action_groups=action_groups)
#         response = parse_response(response)
#         try:
#             print("inline coder response", response)
#             # First check if we have a proper dictionary structure
#             if isinstance(response.get('result'), dict):
#                 generated_code = response['result'].get('code', "No code generated")
#             else:
#                 # Handle raw string responses
#                 generated_code = str(response.get('result', "No code generated"))
                
#             # Additional validation for empty results
#             if generated_code.strip() in {"", "{}", "No code generated"}:
#                 generated_code = "Code generation failed - empty response"
#         except AttributeError as ae:
#             logger.warning(f"Code structure error: {str(ae)}")
#             generated_code = "Invalid code format received from agent"
#         return {
#             "generated_code": generated_code,
#             "current_agent": "supervisor",
#             "tasks_completed": state_dict.get('tasks_completed', []) + ["coder"],#state.get('tasks_completed', []) + ["coder"]
#         }
        
#     except Exception as e:
#         logger.error(f"Inline coder agent error: {str(e)}")
#         return {
#             "error": f"Code generation failed: {str(e)}",
#             "current_agent": "supervisor",
#             "tasks_completed": state.get('tasks_completed', [])
#         }

def inline_coder_agent(state: WorkflowState) -> Dict:
    """
    Inline agent for code generation
    """
    logger.info("Inline coder agent processing")
    
    try:
        agent = InlineAgent()
        action_groups = InlineAgentActions.get_code_actions()
        
        # Use state directly as dictionary
        state_dict = state if isinstance(state, dict) else dict(state)
        logger.debug(f"State dictionary: {state_dict}")
        
        prompt = f"""
        As an AWS developer, generate implementation code for the following architecture.
        Return your response in valid JSON format.

        Requirements:
        {state_dict['user_requirements']}

        Architecture:
        {json.dumps(state.get('architecture_components', {}), indent=2)}

        Return ONLY a JSON object with this structure:
        {{
            "code": {{
                "infrastructure": "// AWS CDK code here",
                "application": "// Application code here",
                "deployment": "// Deployment scripts here",
                "readme": "// Setup instructions here"
            }},
            "explanation": "Brief explanation of the implementation"
        }}
        """
        
        response = agent.invoke(prompt=prompt)
        parsed_response = parse_response(response)
        
        if not parsed_response:
            logger.error("Empty or invalid response from code generation")
            return {
                "error": "Failed to generate valid code response",
                "current_agent": "supervisor",
                "tasks_completed": state_dict.get('tasks_completed', [])
            }
            
        try:
            if isinstance(parsed_response.get('code'), dict):
                generated_code = parsed_response['code']
            else:
                generated_code = {"code": str(parsed_response.get('code', "No code generated"))}
                
            return {
                "generated_code": generated_code,
                "code_explanation": parsed_response.get('explanation', ''),
                "current_agent": "supervisor",
                "tasks_completed": state_dict.get('tasks_completed', []) + ["coder"]
            }
            
        except AttributeError as ae:
            logger.error(f"Code structure error: {str(ae)}")
            return {
                "error": "Invalid code format received from agent",
                "current_agent": "supervisor",
                "tasks_completed": state_dict.get('tasks_completed', [])
            }
            
    except Exception as e:
        logger.error(f"Inline coder agent error: {str(e)}", exc_info=True)
        return {
            "error": f"Code generation failed: {str(e)}",
            "current_agent": "supervisor",
            "tasks_completed": state.get('tasks_completed', [])
        }


def create_inline_architect_agent() -> InlineAgent:
    """Create an inline agent for architecture design"""
    agent = InlineAgent()
    
    instruction = """
    You are an AWS Solutions Architect expert. Your task is to:
    1. Analyze user requirements
    2. Design AWS architecture
    3. Create architecture diagrams
    4. Provide component descriptions
    5. Follow AWS best practices
    
    Use appropriate AWS services and ensure secure, scalable designs.
    """
    
    return agent

def create_inline_coder_agent() -> InlineAgent:
    """Create an inline agent for code generation"""
    agent = InlineAgent()
    
    instruction = """
    You are an expert AWS developer. Your task is to:
    1. Generate implementation code
    2. Create Infrastructure as Code
    3. Write deployment scripts
    4. Add documentation
    5. Follow AWS best practices
    
    Ensure code is production-ready, secure, and well-documented.
    """
    
    return agent

def create_workflow_diagram() -> graphviz.Digraph:
    """Create a visualization of the LangGraph workflow"""
    dot = graphviz.Digraph(comment='LangGraph Workflow')
    dot.attr(rankdir='LR')
    
    # Node styles
    dot.attr('node', shape='box', style='rounded,filled')
    
    # Add nodes with different colors
    dot.node("START", "START", shape='circle', fillcolor='lightgreen')
    dot.node("supervisor", "Supervisor\nAgent", fillcolor='lightblue')
    dot.node("requirements_analyzer", "Requirements\nAnalyzer", fillcolor='lightyellow')
    dot.node("architect", "Architecture\nDesigner", fillcolor='lightpink')
    dot.node("coder", "Code\nGenerator", fillcolor='lightcyan')
    dot.node("explainer", "Code\nExplainer", fillcolor='lightgrey')
    dot.node("consolidator", "Output\nConsolidator", fillcolor='lightsalmon')
    dot.node("END", "END", shape='doublecircle', fillcolor='coral')
    
    # Add edges with descriptions
    dot.edge("START", "supervisor", "Initialize")
    dot.edge("supervisor", "requirements_analyzer", "Analyze")
    dot.edge("requirements_analyzer", "supervisor", "Complete")
    dot.edge("supervisor", "architect", "Design")
    dot.edge("architect", "supervisor", "Complete")
    dot.edge("supervisor", "coder", "Generate")
    dot.edge("coder", "supervisor", "Complete")
    dot.edge("supervisor", "explainer", "Explain")
    dot.edge("explainer", "supervisor", "Complete")
    dot.edge("supervisor", "consolidator", "Consolidate")
    dot.edge("consolidator", "END", "Complete")
    
    return dot

# def save_to_conversation_history(state: WorkflowState, entry: ConversationEntry) -> WorkflowState:
#     """Save the current interaction to conversation history"""
#     if 'conversation_history' not in state:
#         state['conversation_history'] = []
#     state['conversation_history'].append(asdict(entry))
#     return state


class MCPServer:
    """MCP Server configuration and management"""
    
    def __init__(self, server_config: Dict):
        self.name = server_config.get('name')
        self.command = server_config.get('command', 'uvx')
        self.args = server_config.get('args', [])
        self.env = server_config.get('env', {})
        self.auto_approve = server_config.get('autoApprove', [])
        self.disabled = server_config.get('disabled', False)
        self.process = None
    
    def start(self):
        """Start the MCP server"""
        if self.disabled:
            logger.info(f"MCP server {self.name} is disabled")
            return
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.env)
            
            # Start server process
            self.process = subprocess.Popen(
                [self.command] + self.args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"Started MCP server {self.name}")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server {self.name}: {str(e)}")
            raise
    
    def stop(self):
        """Stop the MCP server"""
        if self.process:
            self.process.terminate()
            self.process = None
            logger.info(f"Stopped MCP server {self.name}")

class MCPManager:
    """Manage multiple MCP servers"""
    
    def __init__(self):
        self.servers = {}
        self.load_config()
    
    def load_config(self):
        """Load MCP server configurations"""
        config = {
            "mcpServers": {
                "awslabs.core-mcp-server": {
                    "command": "uvx",
                    "args": [
                        "awslabs.core-mcp-server@latest"
                    ],
                    "env": {
                        "FASTMCP_LOG_LEVEL": "ERROR",
                        "MCP_SETTINGS_PATH": os.getenv("MCP_SETTINGS_PATH", "")
                    },
                    "autoApprove": [],
                    "disabled": False
                },
                "awslabs.bedrock-kb-retrieval-mcp-server": {
                    "command": "uvx",
                    "args": ["awslabs.bedrock-kb-retrieval-mcp-server@latest"],
                    "env": {
                        "AWS_PROFILE": os.getenv("AWS_PROFILE", "default"),
                        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1")
                    }
                },
                "awslabs.cdk-mcp-server": {
                    "command": "uvx",
                    "args": ["awslabs.cdk-mcp-server@latest"],
                    "env": {
                        "FASTMCP_LOG_LEVEL": "ERROR"
                    }
                },
                "awslabs.cost-analysis-mcp-server": {
                    "command": "uvx",
                    "args": ["awslabs.cost-analysis-mcp-server@latest"],
                    "env": {
                        "FASTMCP_LOG_LEVEL": "ERROR"
                    }
                },
                "awslabs.nova-canvas-mcp-server": {
                    "command": "uvx",
                    "args": ["awslabs.nova-canvas-mcp-server@latest"],
                    "env": {
                        "AWS_PROFILE": os.getenv("AWS_PROFILE", "default"),
                        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1")
                    }
                }
            }
        }
        
        for name, server_config in config["mcpServers"].items():
            server_config["name"] = name
            self.servers[name] = MCPServer(server_config)
    
    def start_servers(self):
        """Start all configured MCP servers"""
        for server in self.servers.values():
            server.start()
    
    def stop_servers(self):
        """Stop all running MCP servers"""
        for server in self.servers.values():
            server.stop()

class MCPEnabledAgent:
    """Base class for agents with MCP capabilities"""
    
    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
    
    def _get_mcp_context(self, server_name: str) -> Dict:
        """Get context from specific MCP server"""
        server = self.mcp_manager.servers.get(server_name)
        if not server or server.disabled:
            return {}
        
        # Implement MCP context retrieval logic here
        return {}

def mcp_architect_agent(state: WorkflowState) -> Dict:
    """
    Architect agent with MCP capabilities
    """
    logger.info("MCP architect agent processing")
    
    try:
        # Initialize MCP manager
        mcp_manager = MCPManager()
        mcp_manager.start_servers()
        
        # Create agent with MCP capabilities
        agent = MCPEnabledAgent(mcp_manager)
        
        # Get CDK context
        cdk_context = agent._get_mcp_context("awslabs.cdk-mcp-server")
        
        # Get cost analysis context
        cost_context = agent._get_mcp_context("awslabs.cost-analysis-mcp-server")
        
        # Enhanced prompt with MCP context
        prompt = f"""
        As an AWS Solutions Architect, design a detailed architecture for the following requirements:
        
        Requirements:
        {state['user_requirements']}
        
        CDK Context:
        {json.dumps(cdk_context, indent=2)}
        
        Cost Analysis Context:
        {json.dumps(cost_context, indent=2)}
        
        Create a complete AWS architecture design including:
        1. Required AWS services
        2. Service configurations
        3. Interactions between services
        4. Security considerations
        5. Scalability aspects
        6. Cost optimization
        """
        
        # Use inline agent for generation
        inline_agent = InlineAgent()
        response = inline_agent.invoke(prompt=prompt)
        
        components = response.get('result', {}).get('architecture', {})
        if not components:
            components = response.get('result', {})
        
        dot = generate_aws_architecture_diagram(components)
        
        # Stop MCP servers
        mcp_manager.stop_servers()
        
        return {
            "architecture_components": components,
            "diagram_code": dot.source,
            "current_agent": "supervisor",
            "tasks_completed": state.get('tasks_completed', []) + ["architect"]
        }
        
    except Exception as e:
        logger.error(f"MCP architect agent error: {str(e)}")
        return {
            "error": f"Architecture generation failed: {str(e)}",
            "current_agent": "supervisor",
            "tasks_completed": state.get('tasks_completed', [])
        }


class SupervisorDecision(TypedDict):
    next_agent: str
    reason: str


# Add nodes with better error handling
def wrap_agent(agent_func):
    """Wrapper to ensure consistent state handling and error recovery"""
    def wrapped(state: WorkflowState) -> Dict:
        try:
            result = agent_func(state)
            # Ensure we always have the minimum required fields
            return {
                **state,  # Preserve existing state
                **result,  # Add new results
                "current_agent": result.get("current_agent", "supervisor"),  # Ensure we have next agent
                "tasks_completed": result.get("tasks_completed", state.get("tasks_completed", []))
            }
        except Exception as e:
            logger.error(f"Error in {agent_func.__name__}: {str(e)}")
            return {
                **state,
                "error": f"Error in {agent_func.__name__}: {str(e)}",
                "current_agent": "supervisor"
            }
    return wrapped

def invoke_claude(prompt: str, max_tokens: int = 2000, temperature: float = 0.5) -> str:
    """Invoke Claude with the given prompt"""
    try:
        if TRUNCATE_TOKENS:
            # Reserve tokens for system message and response
            system_reserve = 500
            response_reserve = 1000
            available_tokens = max_tokens - (system_reserve + response_reserve)
        logger.info(f"Invoking Claude with prompt length: {len(prompt)} characters")
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": prompt[:available_tokens]
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        })
        
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            body=body
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body.get('content')[0].get('text', '').strip()
    except Exception as e:
        logger.error(f"Error invoking Claude: {str(e)}")
        return f"Error generating response: {str(e)}"

def supervisor_agent(state: WorkflowState) -> Dict:
    """
    Supervisor agent that decides which task agent should run next
    """
    logger.info("Supervisor agent analyzing current state")
    
    tasks_completed = state.get('tasks_completed', [])
    current_state = {
        **state,  # Preserve existing state
        "tasks_completed": tasks_completed
    }
    
    # Define the task sequence
    task_sequence = [
        "requirements_analyzer",
        "architect",
        "coder",
        "explainer",
        "consolidator"
    ]
    
    # Find the next task that hasn't been completed
    for task in task_sequence:
        if task not in tasks_completed:
            logger.info(f"Next task: {task}")
            return {
                **current_state,  # Keep existing state
                "current_agent": task,  # Set next agent
                "tasks_completed": tasks_completed  # Preserve completed tasks
            }
    
    # If all tasks are completed
    logger.info("All tasks completed")
    return {
        **current_state,
        "current_agent": "end"
    }


def requirements_analyzer_agent(state: WorkflowState) -> Dict:
    """
    Agent responsible for analyzing requirements
    """
    logger.info("Requirements analyzer agent processing")
    
    prompt = f"""
    As a senior software engineer, analyze these requirements and break them down into clear technical specifications:

    User Requirements:
    {state['user_requirements']}

    Provide a detailed analysis including:
    1. Main components/features needed
    2. Technical approach
    3. Any potential challenges
    4. Required libraries/dependencies
    """
    
    analysis = invoke_claude(prompt)
    tasks_completed = state.get('tasks_completed', [])
    
    return {
        "requirements_analysis": analysis,
        "current_agent": "supervisor",
        "tasks_completed": tasks_completed + ["requirements_analyzer"]
    }


def generate_aws_architecture_diagram(components: Dict) -> graphviz.Digraph:
    """Generate AWS architecture diagram using Graphviz"""
    dot = graphviz.Digraph(comment='AWS Architecture Diagram')
    dot.attr(rankdir='LR')
    
    # AWS service icons and colors
    aws_styles = {
        'Lambda': {'shape': 'rectangle', 'color': 'orange', 'style': 'filled'},
        'DynamoDB': {'shape': 'cylinder', 'color': 'blue', 'style': 'filled'},
        'S3': {'shape': 'folder', 'color': 'brown', 'style': 'filled'},
        'API Gateway': {'shape': 'diamond', 'color': 'lightblue', 'style': 'filled'},
        'Cognito': {'shape': 'hexagon', 'color': 'purple', 'style': 'filled'},
        'CloudFront': {'shape': 'triangle', 'color': 'lightgrey', 'style': 'filled'},
        'VPC': {'shape': 'cloud', 'color': 'grey', 'style': 'filled'},
        'ECS': {'shape': 'box3d', 'color': 'orange', 'style': 'filled'},
        'EKS': {'shape': 'box3d', 'color': 'yellow', 'style': 'filled'},
        'RDS': {'shape': 'cylinder', 'color': 'blue', 'style': 'filled'},
        'Aurora': {'shape': 'cylinder', 'color': 'lightblue', 'style': 'filled'},
        'CloudWatch': {'shape': 'note', 'color': 'lightgreen', 'style': 'filled'},
        'X-Ray': {'shape': 'note', 'color': 'pink', 'style': 'filled'}
    }
    
    # Add nodes with AWS styling
    for name, details in components['nodes'].items():
        service = details.get('service', 'Unknown')
        style = aws_styles.get(service, {'shape': 'box', 'color': 'white', 'style': 'filled'})
        
        label = f"{service}\n{name}\n{details.get('description', '')}"
        dot.node(name, label, **style)
    
    # Add edges with protocols
    for edge in components['edges']:
        label = f"{edge['label']}\n({edge.get('protocol', 'N/A')})"
        dot.edge(edge['from'], edge['to'], label)
    
    return dot

def save_diagram(dot: graphviz.Digraph, name: str, formats: List[str] = ['pdf', 'png', 'svg']) -> Dict[str, str]:
    """
    Save diagram in multiple formats and return their paths
    
    Args:
        dot: Graphviz diagram object
        name: Base name for the files
        formats: List of formats to save (pdf, png, svg supported)
    
    Returns:
        Dictionary with format as key and file path as value
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{name}_{timestamp}"
    output_dir = "generated_diagrams"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = {}
    for fmt in formats:
        try:
            filename = base_filename  # Remove .{fmt} since render() adds it
            filepath = os.path.join(output_dir, filename)
            dot.render(filepath, format=fmt, cleanup=True)
            # The actual file will be saved as {filepath}.{fmt}
            saved_files[fmt] = f"{filepath}.{fmt}"
            logger.info(f"Saved diagram as {filepath}.{fmt}")
        except Exception as e:
            logger.error(f"Failed to save {fmt} format: {str(e)}")
    
    return saved_files

def get_diagram_base64(file_path: str) -> str:
    """Convert diagram file to base64 string"""
    try:
        with open(file_path, "rb") as file:
            return base64.b64encode(file.read()).decode()
    except Exception as e:
        logger.error(f"Failed to convert diagram to base64: {str(e)}")
        return ""

def architect_agent(state: WorkflowState) -> Dict:
    """
    Agent responsible for creating AWS architecture diagrams
    """
    logger.info("Architect agent processing")
    
    prompt = f"""
    As a senior AWS solutions architect, analyze these requirements and create a detailed AWS architecture:

    Requirements:
    {state['user_requirements']}

    Analysis:
    {state.get('requirements_analysis', '')}

    Provide the architecture components in the following JSON format:
    {{
        "nodes": {{
            "component_name": {{
                "type": "aws_service",
                "service": "<AWS Service Name>",
                "description": "description",
                "config": {{
                    "key": "value"  // Service-specific configuration
                }}
            }}
        }},
        "edges": [
            {{
                "from": "component_name",
                "to": "component_name",
                "label": "interaction description",
                "protocol": "protocol used"
            }}
        ]
    }}

Use appropriate AWS services for:
- Compute (Lambda, ECS, EKS)
- Storage (S3, EFS, EBS)
- Database (DynamoDB, RDS, Aurora)
- Networking (VPC, API Gateway, CloudFront)
- Security (Cognito, IAM, KMS)
- Monitoring (CloudWatch, X-Ray)

Return only the JSON without additional text.
    """
    
    components_json = invoke_claude(prompt)
    tasks_completed = state.get('tasks_completed', [])
    
    try:
        components = json.loads(components_json)
        dot = generate_aws_architecture_diagram(components)
        # Generate a name for the diagram based on the first service or default
        first_service = next(iter(components['nodes'].values()))['service'] if components['nodes'] else 'architecture'
        diagram_name = f"aws_{first_service.lower()}_architecture"
        
        # Save diagram in multiple formats
        saved_files = save_diagram(dot, diagram_name, formats=['pdf', 'png', 'svg'])
        
        # Add diagram information to components
        components['diagram_files'] = saved_files
        
        # Add base64 encoded versions for web display
        components['diagram_base64'] = {
            fmt: get_diagram_base64(filepath)
            for fmt, filepath in saved_files.items()
        }
        return {
            "architecture_components": components,
            "diagram_code": dot.source,
            "current_agent": "supervisor",
            "tasks_completed": tasks_completed + ["architect"]
        }
    except Exception as e:
        logger.error(f"Architect agent error: {str(e)}")
        return {
            "error": f"Architecture generation failed: {str(e)}",
            "current_agent": "supervisor",
            "tasks_completed": tasks_completed
        }

def coder_agent(state: WorkflowState) -> Dict:
    """
    Agent responsible for generating AWS implementation code
    """
    logger.info("Coder agent processing")
    
    prompt = f"""
    Generate production-ready AWS implementation code based on these requirements and architecture:

    Requirements:
    {state['user_requirements']}

    Analysis:
    {state.get('requirements_analysis', '')}

    Architecture:
    {json.dumps(state.get('architecture_components', {}), indent=2)}

    Generate the following files:
    1. Infrastructure as Code (AWS CDK in TypeScript)
    2. Application code (Python/TypeScript based on requirements)
    3. Deployment scripts
    4. README.md with setup and deployment instructions

    For each file:
    - Include all necessary imports
    - Add comprehensive comments
    - Follow AWS best practices
    - Include error handling
    - Add logging
    - Include security considerations

    Return the code as a JSON object with file paths as keys and content as values.
    """
    
    code_json = invoke_claude(prompt)
    tasks_completed = state.get('tasks_completed', [])
    
    try:
        generated_code = json.loads(code_json)
        return {
            "generated_code": generated_code,
            "current_agent": "supervisor",
            "tasks_completed": tasks_completed + ["coder"]
        }
    except Exception as e:
        logger.error(f"Coder agent error: {str(e)}")
        return {
            "error": f"Code generation failed: {str(e)}",
            "current_agent": "supervisor",
            "tasks_completed": tasks_completed
        }

def explainer_agent(state: WorkflowState) -> Dict:
    """
    Agent responsible for explaining the code
    """
    logger.info("Explainer agent processing")
    
    prompt = f"""
    Explain this code and architecture in detail:

    Code:
    {state.get('generated_code', '')}

    Architecture:
    {json.dumps(state.get('architecture_components', {}), indent=2)}

    Include:
    1. Overall architecture and design choices
    2. How each component works
    3. Best practices used
    4. Implementation details
    5. Usage instructions
    """
    
    explanation = invoke_claude(prompt)
    tasks_completed = state.get('tasks_completed', [])
    
    return {
        "code_explanation": explanation,
        "current_agent": "supervisor",
        "tasks_completed": tasks_completed + ["explainer"]
    }

def consolidator_agent(state: WorkflowState) -> Dict:
    """
    Agent responsible for creating final consolidated output
    """
    logger.info("Consolidator agent processing")
    
    final_output = {
        "requirements_analysis": state.get('requirements_analysis', ''),
        "architecture": {
            "components": state.get('architecture_components', {}),
            "diagram": state.get('diagram_code', '')
        },
        "implementation": {
            "code": state.get('generated_code', ''),
            "explanation": state.get('code_explanation', '')
        }
    }
    
    tasks_completed = state.get('tasks_completed', [])
    
    return {
        "final_output": final_output,
        "current_agent": "end",
        "tasks_completed": tasks_completed + ["consolidator"]
    }

def generate_architecture_diagram(components: Dict) -> graphviz.Digraph:
    """Generate architecture diagram using Graphviz"""
    dot = graphviz.Digraph(comment='Architecture Diagram')
    dot.attr(rankdir='LR')
    
    styles = {
        'service': {'shape': 'rectangle', 'style': 'rounded', 'color': 'blue'},
        'database': {'shape': 'cylinder', 'color': 'orange'},
        'storage': {'shape': 'folder', 'color': 'green'},
        'compute': {'shape': 'box3d', 'color': 'red'},
        'network': {'shape': 'diamond', 'color': 'purple'},
        'client': {'shape': 'component', 'color': 'gray'}
    }
    
    # Validate components structure
    if not isinstance(components, dict):
        raise ValueError("Components must be a dictionary")
    if 'nodes' not in components or 'edges' not in components:
        raise ValueError("Components must contain 'nodes' and 'edges' keys")
    
    for name, details in components['nodes'].items():
        node_style = styles.get(details['type'], {})
        dot.node(name, f"{name}\n{details.get('description', '')}", **node_style)
    
    for edge in components['edges']:
        dot.edge(edge['from'], edge['to'], edge.get('label', ''))
    
    return dot

def router(state: WorkflowState) -> str:
    """Route to the next agent based on current_agent"""
    current_agent = state.get("current_agent", "supervisor")
    logger.info(f"Routing to: {current_agent}")
    return current_agent

# Create the workflow
workflow = StateGraph(WorkflowState)

# Add wrapped nodes
workflow.add_node("supervisor", wrap_agent(supervisor_agent))
workflow.add_node("requirements_analyzer", wrap_agent(requirements_analyzer_agent))
workflow.add_node("architect", wrap_agent(architect_agent))
workflow.add_node("coder", wrap_agent(coder_agent))
#workflow.add_node("architect", wrap_agent(inline_architect_agent))  # Use inline agent
#workflow.add_node("architect", wrap_agent(mcp_architect_agent)) 
#workflow.add_node("coder", wrap_agent(inline_coder_agent))  # Use inline agent
workflow.add_node("explainer", wrap_agent(explainer_agent))
workflow.add_node("consolidator", wrap_agent(consolidator_agent))

# Set entry point
workflow.set_entry_point("supervisor")

# Add conditional edges
workflow.add_conditional_edges(
    "supervisor",
    router,
    {
        "requirements_analyzer": "requirements_analyzer",
        "architect": "architect",
        "coder": "coder",
        "explainer": "explainer",
        "consolidator": "consolidator",
        "end": END
    }
)

for agent in ["requirements_analyzer", "architect", "coder", "explainer", "consolidator"]:
    workflow.add_conditional_edges(
        agent,
        router,
        {
            "supervisor": "supervisor",
            "end": END
        }
    )

# Compile the workflow
multi_agent_assistant = workflow.compile()


def run_workflow_debug(requirements: str):
    """
    Run the workflow directly in debug mode
    """
    # Enable debug logging
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("Starting workflow in debug mode")
    
    try:
        # Initialize workflow state
        initial_state = {
            "user_requirements": requirements,
            "current_agent": "requirements_analyzer",
            "tasks_completed": [],
            "architecture_components": {},
            "generated_code": {},
            "explanation": "",
            "final_output": ""
        }
        
        logger.debug(f"Initial state: {json.dumps(initial_state, indent=2)}")
        
        # Run the workflow
        result = multi_agent_assistant.invoke(initial_state)
        
        logger.debug(f"Final result: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # Example usage
    test_requirements = """
    Build a serverless web application with:
    - User authentication
    - API backend
    - Database storage
    - File upload capability
    """
    
    try:
        # Run workflow with test requirements
        result = run_workflow_debug(test_requirements)
        
        # Print final output
        print("\n=== Final Architecture ===")
        print(json.dumps(result.get("architecture_components", {}), indent=2))
        
        print("\n=== Generated Code ===")
        print(json.dumps(result.get("generated_code", {}), indent=2))
        
        print("\n=== Explanation ===")
        print(result.get("explanation", ""))
        
    except Exception as e:
        print(f"Error: {str(e)}")
