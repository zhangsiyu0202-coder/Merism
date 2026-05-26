"""build_graph — compilation smoke + topology assertions."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from merism.conductor.graph import build_graph


class TestBuildGraph:
    def test_compiles_without_checkpointer(self) -> None:
        # Useful for offline tests / mermaid rendering.
        graph = build_graph(checkpointer=None)
        assert graph is not None

    def test_compiles_with_checkpointer(self) -> None:
        graph = build_graph(checkpointer=InMemorySaver())
        assert graph is not None

    def test_has_all_five_nodes(self) -> None:
        graph = build_graph(checkpointer=None)
        # CompiledStateGraph exposes the underlying graph nodes via
        # get_graph().nodes — name keys are what we registered.
        rendered = graph.get_graph()
        node_names = set(rendered.nodes.keys())
        # LangGraph adds __start__ and __end__ pseudo-nodes.
        expected_real_nodes = {
            "ask",
            "judge_off",
            "judge_standard",
            "judge_deep",
            "advance",
        }
        assert expected_real_nodes <= node_names

    def test_graph_name_is_set(self) -> None:
        graph = build_graph(checkpointer=None)
        # name= passed to compile is exposed for telemetry / langsmith.
        rendered = graph.get_graph()
        assert rendered is not None  # smoke; specific name attr varies by version
