# test_websocket.py
from client import SQLDebugEnv

def test():
    # Use WebSocket URL
    env = SQLDebugEnv(base_url="ws://localhost:8000")
    
    try:
        for task_id in ["syntax_fix_002", "logic_fix_002", "optimize_002", "pipeline_audit_001"]:
            print(f"\n{'='*60}")
            print(f"Testing: {task_id}")
            
            # Connect and reset
            result = env.reset(task_id=task_id)
            obs = result.observation
            
            print(f"✓ task_id: {obs.task_id}")
            print(f"✓ description: {obs.target_description[:50]}...")
            print(f"✓ query: {obs.current_query[:60]}...")
            
            # Try one step
            from models import SQLDebugAction
            result = env.step(SQLDebugAction(query="SELECT 1"))
            print(f"✓ step reward: {result.reward}")
            
    finally:
        env.close()

test()
