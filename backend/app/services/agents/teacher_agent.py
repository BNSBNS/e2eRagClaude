"""
LangGraph Teacher Agent
Adaptive teaching system using state machine
"""

from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI
from core.config import settings
import structlog

logger = structlog.get_logger()

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class TeacherState(TypedDict):
    """State that flows through the teaching graph"""
    document_text: str
    document_id: int
    topic: str
    difficulty: str
    lesson_plan: List[str]
    current_lesson: int
    explanation: str
    problem: str
    student_answer: str
    is_correct: bool
    feedback: str
    retry_count: int
    chat_history: List[dict]
    total_cost: float


class TeacherAgent:
    """Adaptive teaching agent using LangGraph"""
    
    def __init__(self):
        self.workflow = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the teaching state machine"""
        workflow = StateGraph(TeacherState)
        
        # Add nodes
        workflow.add_node("analyze_content", self._analyze_content)
        workflow.add_node("plan_curriculum", self._plan_curriculum)
        workflow.add_node("explain_concept", self._explain_concept)
        workflow.add_node("generate_practice", self._generate_practice)
        
        # Define edges for initial flow
        workflow.add_edge("analyze_content", "plan_curriculum")
        workflow.add_edge("plan_curriculum", "explain_concept")
        workflow.add_edge("explain_concept", "generate_practice")
        workflow.add_edge("generate_practice", END)  # Initial flow ends here
        
        # Set entry point
        workflow.set_entry_point("analyze_content")
        
        return workflow.compile()
    
    async def _analyze_content(self, state: TeacherState) -> TeacherState:
        """Analyze document to understand topic and difficulty"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert educational content analyst."},
                {"role": "user", "content": f"""Analyze this educational content and identify:
1. Main topic
2. Difficulty level (beginner/intermediate/advanced)
3. Prerequisites needed

Content (first 2000 chars):
{state['document_text'][:2000]}

Respond in JSON format:
{{"topic": "...", "difficulty": "...", "prerequisites": ["..."]}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        analysis = json.loads(response.choices[0].message.content)
        
        state['topic'] = analysis['topic']
        state['difficulty'] = analysis['difficulty']
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Content analyzed", topic=state['topic'], difficulty=state['difficulty'])
        return state
    
    async def _plan_curriculum(self, state: TeacherState) -> TeacherState:
        """Create structured lesson plan"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert curriculum designer."},
                {"role": "user", "content": f"""Create a 5-lesson curriculum for teaching: {state['topic']}
Difficulty level: {state['difficulty']}

Return a JSON object with lessons array:
{{"lessons": ["Lesson 1: ...", "Lesson 2: ...", ...]}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        state['lesson_plan'] = result.get('lessons', [])
        state['current_lesson'] = 0
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Curriculum planned", lessons=len(state['lesson_plan']))
        return state
    
    async def _explain_concept(self, state: TeacherState) -> TeacherState:
        """Teach current lesson with examples"""
        lesson = state['lesson_plan'][state['current_lesson']]
        
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an excellent teacher who explains concepts clearly with examples."},
                {"role": "user", "content": f"""Teach this lesson: {lesson}

Use the following content as reference:
{state['document_text'][:3000]}

Provide:
1. Clear explanation
2. Real-world example
3. Key points to remember

Keep it concise and engaging (200-300 words)."""}
            ]
        )
        
        state['explanation'] = response.choices[0].message.content
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Concept explained", lesson=lesson)
        return state
    
    async def _generate_practice(self, state: TeacherState) -> TeacherState:
        """Create practice problem"""
        lesson = state['lesson_plan'][state['current_lesson']]
        
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a teacher creating practice problems."},
                {"role": "user", "content": f"""Create a practice problem for: {lesson}

The problem should:
- Test understanding of the concept
- Be appropriate for {state['difficulty']} level
- Have a clear, verifiable answer

Format:
Problem: [question]
Expected answer: [answer]"""}
            ]
        )
        
        content = response.choices[0].message.content
        # Parse problem and answer
        if "Expected answer:" in content:
            parts = content.split("Expected answer:")
            state['problem'] = parts[0].replace("Problem:", "").strip()
        else:
            state['problem'] = content
        
        state['retry_count'] = 0
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Practice problem generated")
        return state
    
    async def _evaluate_answer(self, state: TeacherState) -> TeacherState:
        """Check if student answer is correct"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a teacher evaluating student answers."},
                {"role": "user", "content": f"""Problem: {state['problem']}

Student answer: {state['student_answer']}

Is this answer correct? Consider partial credit for partially correct answers.

Respond in JSON:
{{"correct": true/false, "explanation": "why correct or incorrect"}}"""}
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        evaluation = json.loads(response.choices[0].message.content)
        state['is_correct'] = evaluation['correct']
        state['feedback'] = evaluation['explanation']
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        logger.info("Answer evaluated", correct=state['is_correct'])
        return state
    
    async def _provide_feedback(self, state: TeacherState) -> TeacherState:
        """Give constructive feedback on wrong answers"""
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a supportive teacher providing feedback."},
                {"role": "user", "content": f"""The student got this problem wrong:

Problem: {state['problem']}
Student answer: {state['student_answer']}
Why wrong: {state['feedback']}

Provide:
1. Encouragement
2. Hint to guide them to the correct answer (don't give it away)
3. Suggestion to try again

Be supportive and constructive."""}
            ]
        )
        
        state['feedback'] = response.choices[0].message.content
        state['retry_count'] += 1
        state['total_cost'] += (response.usage.total_tokens / 1000) * 0.03
        
        return state
    
    async def _congratulate(self, state: TeacherState) -> TeacherState:
        """Celebrate success and move forward"""
        state['feedback'] = f"Excellent work! You've completed: {state['lesson_plan'][state['current_lesson']]}"
        state['current_lesson'] += 1
        state['retry_count'] = 0
        return state
    
    async def start_lesson(self, document_text: str, document_id: int) -> dict:
        """Initialize teaching session"""
        initial_state = TeacherState(
            document_text=document_text,
            document_id=document_id,
            topic="",
            difficulty="",
            lesson_plan=[],
            current_lesson=0,
            explanation="",
            problem="",
            student_answer="",
            is_correct=False,
            feedback="",
            retry_count=0,
            chat_history=[],
            total_cost=0.0
        )
        
        # Run through initial setup (analyze -> plan -> explain -> generate problem)
        result = await self.workflow.ainvoke(initial_state)
        
        return {
            'topic': result['topic'],
            'difficulty': result['difficulty'],
            'lesson_plan': result['lesson_plan'],
            'explanation': result['explanation'],
            'problem': result['problem'],
            'session_id': document_id,
            'cost': result['total_cost']
        }
    
    async def submit_answer(self, state: TeacherState, answer: str) -> dict:
        """Process student answer - called separately, not through graph"""
        state['student_answer'] = answer
        
        # Manually run evaluation (not through graph)
        state = await self._evaluate_answer(state)
        
        if state['is_correct']:
            state = await self._congratulate(state)
            
            # Generate next lesson if available
            if state['current_lesson'] < len(state['lesson_plan']):
                state = await self._explain_concept(state)
                state = await self._generate_practice(state)
            else:
                state['feedback'] = "Congratulations! You've completed all lessons!"
        else:
            state = await self._provide_feedback(state)
        
        return {
            'is_correct': state['is_correct'],
            'feedback': state['feedback'],
            'next_problem': state.get('problem', None),
            'next_explanation': state.get('explanation', None),
            'current_lesson': state['current_lesson'],
            'total_lessons': len(state['lesson_plan']),
            'cost': state['total_cost']
        }


# Global instance
teacher_agent = TeacherAgent()