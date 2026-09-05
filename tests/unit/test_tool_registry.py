import pytest
import asyncio
from packages.rag_pipeline.src.tool_registry import ToolRegistry, SideEffectClass

@pytest.mark.asyncio
async def test_tool_registry_irreversible_blocked_in_replay():
    registry = ToolRegistry()
    
    async def destroy_db():
        return {"status": "destroyed"}
        
    registry.register_tool(
        name="destroy_db",
        handler=destroy_db,
        side_effect_class=SideEffectClass.IRREVERSIBLE,
        replay_policy="block"
    )
    
    # Should work when not in replay
    res = await registry.execute_tool("destroy_db")
    assert res == {"status": "destroyed"}
    
    # Should raise RuntimeError when in replay
    with pytest.raises(RuntimeError, match="Cannot blindly replay irreversible tool"):
        await registry.execute_tool("destroy_db", is_replay=True)

def test_tool_registry_irreversible_blocked_sync():
    registry = ToolRegistry()
    
    def drop_table():
        return {"status": "dropped"}
        
    registry.register_tool(
        name="drop_table",
        handler=drop_table,
        side_effect_class=SideEffectClass.IRREVERSIBLE,
    )
    
    # Sync execute
    res = registry.execute_tool_sync("drop_table")
    assert res == {"status": "dropped"}
    
    with pytest.raises(RuntimeError, match="Cannot blindly replay irreversible tool"):
        registry.execute_tool_sync("drop_table", is_replay=True)
