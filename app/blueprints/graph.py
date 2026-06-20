"""Knowledge graph blueprint (Task 17.4; Requirements 19.4, 19.5).

Serves a case's knowledge-graph nodes and edges, and, when a node is selected,
its details and directly connected nodes.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, request

graph_bp = Blueprint("graph", __name__, url_prefix="/api/v1/cases")


def _session():
    db = current_app.extensions.get("db")
    return db() if db else None


@graph_bp.get("/<uuid:case_id>/graph")
def get_graph(case_id: uuid.UUID):
    session = _session()
    node_id = request.args.get("node")
    if node_id:
        from app.services.knowledge_graph_service import neighborhood

        return jsonify(neighborhood(case_id, node_id, session=session))

    if session is None:
        return jsonify({"nodes": [], "edges": []})

    from app.models.knowledge_graph import KGEdge, KGNode

    nodes = session.query(KGNode).filter(KGNode.case_id == case_id).all()
    edges = session.query(KGEdge).filter(KGEdge.case_id == case_id).all()
    return jsonify(
        {
            "nodes": [
                {"id": str(n.id), "type": n.node_type.value, "label": n.label}
                for n in nodes
            ],
            "edges": [
                {
                    "src": str(e.src_node_id),
                    "dst": str(e.dst_node_id),
                    "relation": e.relation,
                }
                for e in edges
            ],
        }
    )
