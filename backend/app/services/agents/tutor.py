# app/services/agents/tutor.py
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import Command
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from typing import Literal

class EducationalTutorAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.7)
        self.student_profiles = {}
        
    def create_tutor_graph(self):
        def assess_student(state: MessagesState) -> Command[Literal["adapt_content", "provide_help"]]:
            # Analyze student's current understanding
            assessment_prompt = SystemMessage(
                "Analyze the student's question and determine their knowledge level. "
                "Respond with 'beginner', 'intermediate', or 'advanced'."
            )
            
            response = self.llm.invoke([assessment_prompt] + state["messages"])
            level = response.content.lower().strip()
            
            return Command(
                goto="adapt_content",
                update={"student_level": level}
            )
        
        def adapt_content(state: MessagesState) -> Command[Literal["provide_help"]]:
            # Adapt explanation to student level
            level = state.get("student_level", "intermediate")
            
            adaptation_prompt = SystemMessage(f"""
            Provide an explanation suitable for a {level} level student.
            Use appropriate examples and analogies for their level.
            Break down complex concepts into digestible parts.
            """)
            
            response = self.llm.invoke([adaptation_prompt] + state["messages"])
            
            return Command(
                goto="provide_help",
                update={"adapted_content": response.content}
            )
        
        def provide_socratic_help(state: MessagesState) -> Command[Literal["END"]]:
            # Use Socratic method to guide learning
            socratic_prompt = SystemMessage("""
            Instead of giving direct answers, ask guiding questions that help 
            the student discover the answer themselves. Use the Socratic method
            to promote critical thinking and deeper understanding.
            """)
            
            response = self.llm.invoke([socratic_prompt] + state["messages"])
            
            return Command(
                goto="END",
                update={"messages": state["messages"] + [response]}
            )
        
        # Build the tutor graph
        tutor_graph = StateGraph(MessagesState)
        tutor_graph.add_node("assess", assess_student)
        tutor_graph.add_node("adapt_content", adapt_content)  
        tutor_graph.add_node("provide_help", provide_socratic_help)
        
        tutor_graph.add_edge("START", "assess")
        tutor_graph.add_edge("adapt_content", "provide_help")
        
        return tutor_graph.compile()
    
    async def tutor_session(self, question: str, user_id: str) -> str:
        graph = self.create_tutor_graph()
        
        result = await graph.ainvoke({
            "messages": [HumanMessage(content=question)]
        })
        
        return result["messages"][-1].content