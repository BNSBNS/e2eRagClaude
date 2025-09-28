# app/core/monitoring.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST
import time

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds', 
    'HTTP request duration',
    ['method', 'endpoint']
)

LLM_TOKEN_USAGE = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'type']  # type: input/output
)

LLM_COST = Counter(
    'llm_cost_usd_total',
    'Total LLM costs in USD',
    ['model']
)

ACTIVE_USERS = Gauge(
    'active_users_current',
    'Currently active users'
)

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                REQUEST_COUNT.labels(
                    method=scope["method"],
                    endpoint=scope["path"],
                    status=message["status"]
                ).inc()
                
                REQUEST_DURATION.labels(
                    method=scope["method"],
                    endpoint=scope["path"]
                ).observe(time.time() - start_time)
            
            await send(message)

        await self.app(scope, receive, send_wrapper)

def track_llm_usage(model: str, input_tokens: int, output_tokens: int, cost: float):
    LLM_TOKEN_USAGE.labels(model=model, type="input").inc(input_tokens)
    LLM_TOKEN_USAGE.labels(model=model, type="output").inc(output_tokens)
    LLM_COST.labels(model=model).inc(cost)

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)