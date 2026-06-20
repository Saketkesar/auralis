"""Knowledge-graph ORM models: KGNode and KGEdge.

Findings are linked into a navigable graph of typed nodes and relationship
edges (Requirements 19.1, 19.2). Edges reference nodes within the same Case;
deleting a node cascades to its incident edges.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import NodeType
from app.models.types import jsonb, pg_enum


class KGNode(Base):
    """A typed node in a Case knowledge graph (Requirement 19.1)."""

    __tablename__ = "kg_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type: Mapped[NodeType] = mapped_column(
        pg_enum(NodeType, "kg_node_type"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    props: Mapped[dict[str, Any] | None] = mapped_column(jsonb(), nullable=True)

    case: Mapped["Case"] = relationship(back_populates="kg_nodes")  # noqa: F821
    out_edges: Mapped[list["KGEdge"]] = relationship(
        back_populates="src_node",
        foreign_keys="KGEdge.src_node_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    in_edges: Mapped[list["KGEdge"]] = relationship(
        back_populates="dst_node",
        foreign_keys="KGEdge.dst_node_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KGEdge(Base):
    """A directed relationship between two nodes (Requirement 19.2)."""

    __tablename__ = "kg_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    src_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dst_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation: Mapped[str] = mapped_column(String(128), nullable=False)
    props: Mapped[dict[str, Any] | None] = mapped_column(jsonb(), nullable=True)

    case: Mapped["Case"] = relationship(back_populates="kg_edges")  # noqa: F821
    src_node: Mapped["KGNode"] = relationship(
        back_populates="out_edges", foreign_keys=[src_node_id]
    )
    dst_node: Mapped["KGNode"] = relationship(
        back_populates="in_edges", foreign_keys=[dst_node_id]
    )


__all__ = ["KGNode", "KGEdge"]
