from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain.tools import BaseTool
from langchain.llms import OpenAI
from typing import TypedDict, List, Optional
import json

class AgentState(TypedDict):
    messages: List[dict]
    user_query: str
    context: str
    learning_level: str
    response: str
    needs_more_info: bool

class KnowledgeRetrievalTool(BaseTool):
    name = "knowledge_retrieval"
    description = "Retrieve relevant knowledge from the knowledge base"
    
    def _run(self, query: str) -> str:
        # Integrate with vector RAG service
        return f"Retrieved knowledge for: {query}"

class AssessmentTool(BaseTool):
    name = "assessment"
    description = "Assess student understanding level"
    
    def _run(self, student_response: str) -> str:
        # Analyze student understanding
        return f"Assessment result for: {student_response}"

class EducationalAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0.7)
        self.tools = [KnowledgeRetrievalTool(), AssessmentTool()]
        self.tool_executor = ToolExecutor(self.tools)
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("understand", self.understand_query)
        workflow.add_node("retrieve", self.retrieve_knowledge)
        workflow.add_node("generate", self.generate_response)
        workflow.add_node("assess", self.assess_understanding)
        workflow.add_node("personalize", self.personalize_response)
        
        # Add edges
        workflow.set_entry_point("understand")
        workflow.add_edge("understand", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "assess")
        workflow.add_edge("assess", "personalize")
        workflow.add_edge("personalize", END)
        
        return workflow.compile() 
    
    def understand_query(self, state: AgentState) -> AgentState:
        query = state["user_query"]
        
        understanding_prompt = f"""
        Analyze this educational query and determine:
        1. What the student is trying to learn
        2. Their apparent knowledge level
        3. What type of explanation would be most helpful
        
        Query: {query}
        
        Provide analysis in JSON format:
        {{"topic": "...", "level": "beginner|intermediate|advanced", "explanation_type": "conceptual|practical|theoretical"}}
        """
        
        analysis = self.llm.invoke(understanding_prompt)
        try:
            parsed_analysis = json.loads(analysis)
            state["learning_level"] = parsed_analysis.get("level", "beginner")
            state["context"] = f"Topic: {parsed_analysis.get('topic', 'Unknown')}, Explanation type: {parsed_analysis.get('explanation_type', 'conceptual')}"
        except:
            state["learning_level"] = "beginner"
            state["context"] = "General educational query"
        
        return state
    
    def retrieve_knowledge(self, state: AgentState) -> AgentState:
        # Use knowledge retrieval tool
        knowledge = self.tool_executor.invoke({
            "tool": "knowledge_retrieval",
            "tool_input": state["user_query"]
        })
        
        state["context"] += f"\n\nRetrieved knowledge: {knowledge}"
        return state
    
    def generate_response(self, state: AgentState) -> AgentState:
        generation_prompt = f"""
        You are an expert educational tutor. Generate a response that:
        1. Addresses the student's query directly
        2. Matches their learning level ({state["learning_level"]})
        3. Uses clear, pedagogical explanations
        4. Includes examples when appropriate
        5. Encourages further learning
        
        Query: {state["user_query"]}
        Context: {state["context"]}
        
        Provide a comprehensive, educational response:
        """
        
        response = self.llm.invoke(generation_prompt)
        state["response"] = response
        
        return state
    
    def assess_understanding(self, state: AgentState) -> AgentState:
        # Simple assessment - in production, this would be more sophisticated
        assessment_prompt = f"""
        Based on this educational response, determine if the student might need:
        1. More basic explanation
        2. Additional examples
        3. More advanced concepts
        4. Practice exercises
        
        Response: {state["response"]}
        
        Return "true" if more information is needed, "false" otherwise.
        """
        
        assessment = self.llm.invoke(assessment_prompt)
        state["needs_more_info"] = "true" in assessment.lower()
        
        return state
    
    def personalize_response(self, state: AgentState) -> AgentState:
        if state["needs_more_info"]:
            personalization_prompt = f"""
            The student may need additional support. Enhance this response with:
            1. Simpler explanations if too complex
            2. More examples if too abstract
            3. Encouragement and next steps
            
            Original response: {state["response"]}
            
            Provide an enhanced, more supportive version:
            """
            
            enhanced_response = self.llm.invoke(personalization_prompt)
            state["response"] = enhanced_response
        
        return state
    
    async def process_educational_query(self, query: str) -> dict:
        initial_state = {
            "messages": [],
            "user_query": query,
            "context": "",
            "learning_level": "",
            "response": "",
            "needs_more_info": False
        }
        
        result = self.workflow.invoke(initial_state)
        
        return {
            "query": query,
            "response": result["response"],
            "learning_level": result["learning_level"],
            "context": result["context"],
            "enhanced": result["needs_more_info"]
        }