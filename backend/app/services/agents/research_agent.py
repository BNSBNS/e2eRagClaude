"""
True Agentic Research Assistant
Autonomously searches, synthesizes, and validates information
"""

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI
from core.config import settings
from core.redis_client import cache_get, cache_set
import json
import structlog

logger = structlog.get_logger()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class ResearchState(TypedDict):
    """State for research agent"""
    user_query: str
    document_id: int
    document_text: str
    plan: List[str]
    current_step: int
    findings: List[dict]
    needs_more_info: bool
    final_answer: str
    total_cost: float


class ResearchAgent:
    """Autonomous research agent"""
    
    def __init__(self):
        self.workflow = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ResearchState)
        
        # Add nodes
        workflow.add_node("planner", self._create_plan)
        workflow.add_node("researcher", self._research_step)
        workflow.add_node("validator", self._validate_findings)
        workflow.add_node("synthesizer", self._synthesize_answer)
        
        # Define flow
        workflow.add_edge("planner", "researcher")
        workflow.add_edge("researcher", "validator")
        
        # Conditional: loop back or synthesize
        workflow.add_conditional_edges(
            "validator",
            self._is_complete,
            {
                "continue": "researcher",  # Loop back
                "done": "synthesizer"
            }
        )
        
        workflow.add_edge("synthesizer", END)
        workflow.set_entry_point("planner")
        
        return workflow.compile()
    
    async def _create_plan(self, state: ResearchState) -> ResearchState:
        """Create research plan"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "Create a research plan to answer the question using the document."},
                {"role": "user", "content": f"""Question: {state['user_query']}

Document preview:
{state['document_text'][:2000]}

Create 3-5 research steps. Return JSON:
{{"steps": ["step 1", "step 2", ...]}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        plan_data = json.loads(response.choices[0].message.content)
        state['plan'] = plan_data.get('steps', [])
        state['current_step'] = 0
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Research plan created", steps=len(state['plan']))
        return state
    
    async def _research_step(self, state: ResearchState) -> ResearchState:
        """Execute current research step"""
        if state['current_step'] >= len(state['plan']):
            return state
        
        step = state['plan'][state['current_step']]
        
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are researching from a document."},
                {"role": "user", "content": f"""Research step: {step}

Document:
{state['document_text'][:4000]}

Find relevant information. Return JSON:
{{"finding": "what you found", "confidence": "high/medium/low"}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        finding = json.loads(response.choices[0].message.content)
        state['findings'].append({
            'step': step,
            'finding': finding.get('finding'),
            'confidence': finding.get('confidence')
        })
        
        state['current_step'] += 1
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        return state
    
    async def _validate_findings(self, state: ResearchState) -> ResearchState:
        """Check if we have enough information"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "Validate research completeness."},
                {"role": "user", "content": f"""Question: {state['user_query']}

Findings:
{json.dumps(state['findings'], indent=2)}

Can we answer the question? Return JSON:
{{"complete": true/false, "confidence": 0-100}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        validation = json.loads(response.choices[0].message.content)
        state['needs_more_info'] = not validation.get('complete', False)
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        return state
    
    async def _synthesize_answer(self, state: ResearchState) -> ResearchState:
        """Create final comprehensive answer"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "Synthesize research into a comprehensive answer."},
                {"role": "user", "content": f"""Question: {state['user_query']}

Research findings:
{json.dumps(state['findings'], indent=2)}

Create a well-structured, detailed answer."""}
            ]
        )
        
        state['final_answer'] = response.choices[0].message.content
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        return state
    
    def _is_complete(self, state: ResearchState) -> str:
        """Decision: continue researching or done?"""
        # Max 5 steps to prevent infinite loops
        if state['current_step'] >= min(len(state['plan']), 5):
            return "done"
        return "continue" if state['needs_more_info'] else "done"
    
    async def research(self, document_id: int, document_text: str, query: str) -> dict:
        """Start research process"""
        initial_state = ResearchState(
            user_query=query,
            document_id=document_id,
            document_text=document_text,
            plan=[],
            current_step=0,
            findings=[],
            needs_more_info=True,
            final_answer="",
            total_cost=0.0
        )
        
        result = await self.workflow.ainvoke(initial_state)
        
        return {
            'answer': result['final_answer'],
            'plan': result['plan'],
            'findings': result['findings'],
            'cost': result['total_cost']
        }


# Global instance
research_agent = ResearchAgent()