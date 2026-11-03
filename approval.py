"""Persist and review a proposed support reply without sending it."""

import argparse
import json
from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict, total=False):
    draft: str
    decision: Literal["approve", "edit", "reject"]
    approved_reply: str | None


def review(state: State) -> State:
    response = interrupt({"draft": state["draft"], "choices": ["approve", "edit", "reject"]})
    decision = response["decision"]
    reply = None if decision == "reject" else response.get("text", state["draft"])
    return {"decision": decision, "approved_reply": reply}


def build_graph(checkpointer):
    graph = StateGraph(State)
    graph.add_node("review", review)
    graph.add_edge(START, "review")
    graph.add_edge("review", END)
    return graph.compile(checkpointer=checkpointer)


def status(graph, config):
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise ValueError("Unknown request ID.")
    return {
        "id": config["configurable"]["thread_id"],
        "status": "pending" if snapshot.next else "completed",
        **snapshot.values,
    }


def execute(db, action, *, request_id=None, text=None, decision=None):
    if action == "start" and not (text and text.strip()):
        raise ValueError("A nonblank draft is required.")
    if action == "review":
        if decision not in {"approve", "edit", "reject"}:
            raise ValueError("Choose approve, edit, or reject.")
        if decision == "edit" and not (text and text.strip()):
            raise ValueError("An edited reply is required.")
        if decision != "edit" and text is not None:
            raise ValueError("Replacement text is only accepted with edit.")
    config = {"configurable": {"thread_id": uuid4().hex if action == "start" else request_id}}
    with SqliteSaver.from_conn_string(str(db)) as saver:
        graph = build_graph(saver)
        if action == "start":
            graph.invoke({"draft": text.strip()}, config)
        elif action == "review":
            if status(graph, config)["status"] != "pending":
                raise ValueError("This request has already been reviewed.")
            response = {"decision": decision}
            if decision == "edit":
                response["text"] = text.strip()
            graph.invoke(Command(resume=response), config)
        return status(graph, config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="approvals.sqlite")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("start").add_argument("text")
    commands.add_parser("status").add_argument("request_id")
    review_parser = commands.add_parser("review")
    review_parser.add_argument("request_id")
    review_parser.add_argument("decision", choices=["approve", "edit", "reject"])
    review_parser.add_argument("--text")
    args = vars(parser.parse_args())
    try:
        result = execute(**args)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
