"""Semantic memory service (Neo4j-backed).

This is a lightweight, extensible skeleton implementing two core operations:
- upsert_from_final_bpmn: merge a confirmed BPMN process into the graph
- query_by_nl: run a simple schema-aware search (fulltext index) to return candidates

The implementation is intentionally minimal so you can extend LLM extraction,
advanced entity resolution, and embedding-based retrieval later.
"""
import uuid
from typing import Dict, Any, List

from neo4j import AsyncGraphDatabase
from config import settings


class SemanticMemory:
    def __init__(self):
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        pwd = settings.NEO4J_PASSWORD
        self.database = settings.NEO4J_DATABASE
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, pwd))

    async def close(self):
        await self._driver.close()

    async def ensure_indexes(self):
        """Create needed fulltext indices if they don't exist.

        Best-effort: if the index exists already, Neo4j will raise — we ignore that.
        """
        create_index_cypher = (
            "CALL db.index.fulltext.createNodeIndex('processIndex',['Process'],['name','definition'])"
        )
        async with self._driver.session(database=self.database) as session:
            try:
                await session.run(create_index_cypher)
            except Exception:
                # ignore (likely already exists)
                pass

    async def upsert_from_final_bpmn(
        self,
        process_id: str = None,
        final_bpmn: Dict[str, Any] = None,
        enrichment_text: str = None,
        user_id: str = None,
        source: str = None,
    ) -> Dict[str, Any]:
        """Minimal upsert: create/merge a Process node and link a few basic properties.

        This does NOT perform full entity extraction — it is a starting point.
        Extend this method to call your LLM extraction and the detailed merge
        logic described in the design doc.
        """
        if final_bpmn is None:
            raise ValueError("final_bpmn is required")

        proc_uuid = process_id or str(uuid.uuid4())
        # try to extract a human-friendly name
        name = final_bpmn.get("title") or final_bpmn.get("name") or final_bpmn.get("process_name")
        definition = enrichment_text or final_bpmn.get("description") or ""
        level = final_bpmn.get("level") or 4

        cypher = (
            "MERGE (p:Process {id:$id})\n"
            "ON CREATE SET p.elementId = coalesce($elementId, p.elementId), p.name = $name, p.definition = $definition, p.level = $level\n"
            "ON MATCH SET p.name = CASE WHEN $name IS NOT NULL THEN $name ELSE p.name END, p.definition = CASE WHEN $definition IS NOT NULL THEN $definition ELSE p.definition END\n"
            "RETURN p"
        )

        params = {
            "id": proc_uuid,
            "elementId": final_bpmn.get("elementId"),
            "name": name,
            "definition": definition,
            "level": level,
        }

        async with self._driver.session(database=self.database) as session:
            result = await session.run(cypher, params)
            record = await result.single()

        merged_nodes = {"Process": 1}
        return {
            "status": "ok",
            "merged_nodes": merged_nodes,
            "conflicts": [],
            "process_node_id": proc_uuid,
        }

    async def query_by_nl(self, nl_query: str, schema_hint: List[str] = None, top_k: int = 5) -> Dict[str, Any]:
        """Perform a simple fulltext search over Process name/definition and
        return top_k matching nodes.

        For production you should augment this with embedding re-ranking and
        traversal-based retrieval.
        """
        # Ensure index exists (best-effort)
        await self.ensure_indexes()

        cypher = (
            "CALL db.index.fulltext.queryNodes('processIndex', $query) YIELD node, score\n"
            "RETURN node, score ORDER BY score DESC LIMIT $limit"
        )

        async with self._driver.session(database=self.database) as session:
            result = await session.run(cypher, {"query": nl_query, "limit": top_k})
            records = await result.list()

        results = []
        for rec in records:
            node = rec[0]
            score = rec[1]
            props = dict(node._properties)
            results.append({
                "node": {"label": list(node.labels)[0] if node.labels else "Process", "id": props.get("id"), "name": props.get("name"), "definition": props.get("definition")},
                "score": float(score),
                "properties": props,
            })

        return {"results": results}


# create a module-level singleton for simple import in routers
semantic_memory = SemanticMemory()
