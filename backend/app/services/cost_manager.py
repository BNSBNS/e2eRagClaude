# app/services/cost_manager.py
from typing import Dict, Optional
import asyncio
from datetime import datetime, timedelta
from app.core.redis import redis_client

class CostManager:
    def __init__(self):
        self.daily_budget = 100.0  # USD
        self.model_costs = {
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},  # per 1K tokens
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002}
        }
        
    async def track_usage(self, user_id: str, model: str, input_tokens: int, output_tokens: int):
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        # Track daily spending
        today = datetime.now().strftime("%Y-%m-%d")
        daily_key = f"cost:daily:{today}"
        user_key = f"cost:user:{user_id}:{today}"
        
        await redis_client.incrbyfloat(daily_key, cost)
        await redis_client.incrbyfloat(user_key, cost)
        await redis_client.expire(daily_key, 86400)
        await redis_client.expire(user_key, 86400)
        
        # Check budget
        daily_spend = float(await redis_client.get(daily_key) or 0)
        if daily_spend > self.daily_budget:
            raise HTTPException(429, "Daily budget exceeded")
            
        return cost
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model not in self.model_costs:
            model = "gpt-3.5-turbo"  # Fallback
            
        input_cost = (input_tokens / 1000) * self.model_costs[model]["input"]
        output_cost = (output_tokens / 1000) * self.model_costs[model]["output"]
        
        return input_cost + output_cost
    
    async def get_daily_spending(self) -> Dict[str, float]:
        today = datetime.now().strftime("%Y-%m-%d")
        daily_key = f"cost:daily:{today}"
        
        daily_spend = float(await redis_client.get(daily_key) or 0)
        remaining_budget = max(0, self.daily_budget - daily_spend)
        
        return {
            "daily_spend": daily_spend,
            "daily_budget": self.daily_budget,
            "remaining_budget": remaining_budget,
            "budget_utilization": (daily_spend / self.daily_budget) * 100
        }

# Usage in RAG service
cost_manager = CostManager()

async def process_llm_request(query: str, user_id: str):
    # Check budget before processing
    spending_info = await cost_manager.get_daily_spending()
    if spending_info["remaining_budget"] < 1.0:  # $1 minimum
        return "Daily budget exceeded. Please try again tomorrow."
    
    # Process with OpenAI
    response = await openai_client.chat.completions.create(...)
    
    # Track usage
    await cost_manager.track_usage(
        user_id=user_id,
        model=response.model,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens
    )
    
    return response.choices[0].message.content