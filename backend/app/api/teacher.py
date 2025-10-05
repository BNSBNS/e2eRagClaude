"""
Teacher Agent API
Handles adaptive teaching interactions
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from models.user import User
from api.auth import get_current_active_user
from services.document_service import DocumentService
from services.agents.teacher_agent import teacher_agent, TeacherState
from models.document import DocumentStatus
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Request/Response Models
class StartTeachingRequest(BaseModel):
    document_id: int


class SubmitAnswerRequest(BaseModel):
    document_id: int
    answer: str
    session_state: dict  # Client maintains state


class TeachingResponse(BaseModel):
    topic: str
    difficulty: str
    lesson_plan: list[str]
    explanation: str
    problem: str
    session_state: dict
    cost: float


class AnswerResponse(BaseModel):
    is_correct: bool
    feedback: str
    next_problem: str | None
    next_explanation: str | None
    current_lesson: int
    total_lessons: int
    session_state: dict
    cost: float


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/start", response_model=TeachingResponse)
async def start_teaching(
    request: StartTeachingRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Start an adaptive teaching session.
    
    The agent will:
    1. Analyze the document
    2. Create a curriculum
    3. Present the first lesson
    4. Generate a practice problem
    """
    logger.info("Teaching session start", 
               document_id=request.document_id,
               user_id=current_user.id)
    
    # Get document
    document = await DocumentService.get_document_by_id(db, request.document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    # Start teaching session
    result = await teacher_agent.start_lesson(
        document_text=document.extracted_text,
        document_id=document.id
    )
    
    # Return initial state for client to maintain
    session_state = {
        'document_text': document.extracted_text,
        'document_id': document.id,
        'topic': result['topic'],
        'difficulty': result['difficulty'],
        'lesson_plan': result['lesson_plan'],
        'current_lesson': 0,
        'explanation': result['explanation'],
        'problem': result['problem'],
        'retry_count': 0,
        'total_cost': result['cost']
    }
    
    return {
        'topic': result['topic'],
        'difficulty': result['difficulty'],
        'lesson_plan': result['lesson_plan'],
        'explanation': result['explanation'],
        'problem': result['problem'],
        'session_state': session_state,
        'cost': result['cost']
    }


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    request: SubmitAnswerRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit an answer to the current practice problem.
    
    The agent will:
    1. Evaluate the answer
    2. Provide feedback
    3. Either give a hint (wrong) or move to next lesson (correct)
    """
    logger.info("Answer submitted",
               document_id=request.document_id,
               user_id=current_user.id)
    
    # Reconstruct state from client
    state = TeacherState(**request.session_state)
    
    # Process answer
    result = await teacher_agent.submit_answer(state, request.answer)
    
    # Update session state
    session_state = request.session_state.copy()
    session_state['current_lesson'] = result['current_lesson']
    session_state['total_cost'] = result['cost']
    
    if result.get('next_explanation'):
        session_state['explanation'] = result['next_explanation']
        session_state['problem'] = result['next_problem']
        session_state['retry_count'] = 0
    
    return {
        'is_correct': result['is_correct'],
        'feedback': result['feedback'],
        'next_problem': result.get('next_problem'),
        'next_explanation': result.get('next_explanation'),
        'current_lesson': result['current_lesson'],
        'total_lessons': result['total_lessons'],
        'session_state': session_state,
        'cost': result['cost']
    }