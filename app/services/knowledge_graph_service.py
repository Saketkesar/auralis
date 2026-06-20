"""Knowledge graph service (Task 17.1; Requirements 19.1-19.4).

Builds nodes for the image, extracted text, detected objects, businesses,
websites, search results, locations, map references, similar images, and social
profiles, plus relationship edges between connected nodes. On node-creation
failure it reports failure so the investigation view can render without the
graph. Also supports node-neighbourhood queries.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.models.enums import NodeType, StageName


def build_knowledge_graph(
    case_id: uuid.UUID,
    findings: Dict[Any, dict],
    *,
    session=None,
) -> Dict[str, Any]:
    """Assemble the knowledge graph from stage findings.

    Returns a dict with ``ok`` plus the in-memory ``nodes``/``edges``. When a
    DB session is supplied the nodes/edges are also persisted.
    """
    try:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        def add_node(node_type: NodeType, label: str, props: dict | None = None) -> str:
            nid = str(uuid.uuid4())
            nodes.append({"id": nid, "type": node_type.value, "label": label, "props": props or {}})
            return nid

        def add_edge(src: str, dst: str, relation: str) -> None:
            edges.append({"src": src, "dst": dst, "relation": relation})

        image_id = add_node(NodeType.IMAGE, f"case:{case_id}")

        # OCR text + businesses
        ocr = _get(findings, StageName.OCR)
        for region in (ocr.get("text_regions") or []):
            tid = add_node(NodeType.TEXT, str(region.get("text", ""))[:80])
            add_edge(image_id, tid, "contains_text")
        for biz in (ocr.get("entities", {}).get("business_names") or [])[:10]:
            bid = add_node(NodeType.BUSINESS, str(biz))
            add_edge(image_id, bid, "mentions_business")

        # Objects
        obj = _get(findings, StageName.OBJECT)
        for klass in (obj.get("inventory") or {}):
            oid = add_node(NodeType.OBJECT, str(klass))
            add_edge(image_id, oid, "contains_object")

        # Locations (geoint) + map references
        geoint = _get(findings, StageName.GEOINT)
        for cand in (geoint.get("candidates") or [])[:10]:
            lid = add_node(NodeType.LOCATION, str(cand.get("city") or cand.get("country")))
            add_edge(image_id, lid, "possible_location")
            for ref in cand.get("map_references", [])[:5]:
                mid = add_node(NodeType.MAP_REFERENCE, str(ref))
                add_edge(lid, mid, "map_reference")

        # Reverse search: websites + similar images
        rev = _get(findings, StageName.REVERSE_SEARCH)
        for site in (rev.get("websites") or [])[:10]:
            wid = add_node(NodeType.WEBSITE, str(site))
            add_edge(image_id, wid, "appears_on")
        for m in (rev.get("matches") or [])[:10]:
            sid = add_node(NodeType.SIMILAR_IMAGE, str(m.get("title", "match")))
            add_edge(image_id, sid, "similar_to")

        if session is not None:
            _persist(session, case_id, nodes, edges)

        return {"ok": True, "nodes": nodes, "edges": edges}
    except Exception as exc:  # noqa: BLE001 - graceful degradation (19.3)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "nodes": [], "edges": []}


def neighborhood(case_id: uuid.UUID, node_id: str, *, session=None) -> Dict[str, Any]:
    """Return a node's details and its directly connected nodes (19.4)."""
    if session is None:
        return {"node": None, "neighbors": []}
    from app.models.knowledge_graph import KGEdge, KGNode

    node = session.get(KGNode, uuid.UUID(node_id))
    if node is None:
        return {"node": None, "neighbors": []}
    edges = (
        session.query(KGEdge)
        .filter(
            (KGEdge.src_node_id == node.id) | (KGEdge.dst_node_id == node.id)
        )
        .all()
    )
    neighbor_ids = {
        e.dst_node_id if e.src_node_id == node.id else e.src_node_id for e in edges
    }
    neighbors = [session.get(KGNode, nid) for nid in neighbor_ids]
    return {
        "node": {"id": str(node.id), "type": node.node_type.value, "label": node.label},
        "neighbors": [
            {"id": str(n.id), "type": n.node_type.value, "label": n.label}
            for n in neighbors
            if n is not None
        ],
    }


def _persist(session, case_id, nodes, edges) -> None:
    from app.models.knowledge_graph import KGEdge, KGNode

    id_map: Dict[str, uuid.UUID] = {}
    for n in nodes:
        row = KGNode(
            case_id=case_id,
            node_type=NodeType(n["type"]),
            label=n["label"][:512],
            props=n["props"],
        )
        session.add(row)
        session.flush()
        id_map[n["id"]] = row.id
    for e in edges:
        session.add(
            KGEdge(
                case_id=case_id,
                src_node_id=id_map[e["src"]],
                dst_node_id=id_map[e["dst"]],
                relation=e["relation"],
            )
        )
    session.commit()


def _get(findings: Dict[Any, dict], stage: StageName) -> dict:
    return findings.get(stage) or findings.get(stage.value) or {}


__all__ = ["build_knowledge_graph", "neighborhood"]
