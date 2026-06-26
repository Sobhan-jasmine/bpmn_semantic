"""Module 9 - Semantic Memory (Neo4j).

World model built on APQC Process Classification Framework.

This implementation adds:
- LLM-driven strict JSON extraction using the existing llm_service
- Multi-step entity resolution: elementId / id exact match, exact name+level,
  fulltext candidate search, embedding re-ranking
- Storing node embeddings as a property (simple vector store) for re-ranking
- Sync flow to merge extracted nodes and relationships into Neo4j

Notes:
- This is a pragmatic implementation for prototyping. For production:
  - Move embeddings to a dedicated vector DB
  - Add transactional safety and better error handling
  - Add schema validation of LLM output against a JSON schema
"""
from typing import Dict, Any, List, Optional, Tuple
import uuid
import json
import math

from neo4j import AsyncGraphDatabase
from config import settings
from services.llm_service import llm_service
from services.embedding_service import EmbeddingService


class SemanticService:
    """Service for managing semantic memory in Neo4j with LLM/embedding integration."""

    def __init__(self):
        self._driver = None
        self.embedding = EmbeddingService()

    async def connect(self):
        """Connect to Neo4j using Async driver."""
        self._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        # ensure basic fulltext index exists
        await self._ensure_indexes()
        print("Connected to Neo4j")

    async def disconnect(self):
        if self._driver:
            await self._driver.close()
            print("Disconnected from Neo4j")

    async def _ensure_indexes(self):
        create_index_cypher = (
            "CALL db.index.fulltext.createNodeIndex('processIndex',['Process'],['name','definition'])"
        )
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            try:
                await session.run(create_index_cypher)
            except Exception:
                # ignore if already exists
                pass

    async def query_semantic(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query semantic memory: fulltext candidate retrieval + embedding re-rank.

        Returns a list of candidate nodes with score and properties.
        """
        # fulltext candidates
        cypher = (
            "CALL db.index.fulltext.queryNodes('processIndex', $query) YIELD node, score\n"
            "RETURN node, score ORDER BY score DESC LIMIT $limit"
        )
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            res = await session.run(cypher, {"query": query_text, "limit": top_k * 3})
            records = await res.list()

        candidates = []
        texts = []
        for rec in records:
            node = rec[0]
            score = float(rec[1])
            props = dict(node._properties)
            node_id = props.get("id")
            name = props.get("name") or ""
            definition = props.get("definition") or ""
            text = f"{name}. {definition}".strip()
            candidates.append({"node_id": node_id, "props": props, "ft_score": score})
            texts.append(text)

        # compute embedding for query and candidate re-rank if embeddings present
        if candidates:
            try:
                query_emb = await self.embedding.embed([query_text])
                # candidate embeddings: try to use stored embeddings; otherwise compute on the fly
                candidate_embs = []
                for c in candidates:
                    emb = c["props"].get("embedding")
                    if emb:
                        # embedding saved as list -> convert to list[float]
                        candidate_embs.append(emb)
                    else:
                        candidate_embs.append(None)

                # compute missing embeddings in batches
                to_compute = []
                compute_idxs = []
                for i, emb in enumerate(candidate_embs):
                    if emb is None:
                        to_compute.append(texts[i])
                        compute_idxs.append(i)

                if to_compute:
                    computed = await self.embedding.embed(to_compute)
                    # computed may be numpy array
                    computed_list = computed.tolist() if hasattr(computed, "tolist") else list(computed)
                    for idx, val in zip(compute_idxs, computed_list):
                        candidate_embs[idx] = val

                # now compute cosine similarities
                q = query_emb[0] if hasattr(query_emb, "__len__") else query_emb
                reranked = []
                for c, emb in zip(candidates, candidate_embs):
                    if emb is None:
                        sim = 0.0
                    else:
                        sim = _cosine_similarity(q, emb)
                    reranked.append({"node": c["props"], "ft_score": c["ft_score"], "sim": sim})

                # sort by sim then ft_score
                reranked.sort(key=lambda x: (x["sim"], x["ft_score"]), reverse=True)
                return reranked[:top_k]
            except Exception:
                # fallback to fulltext order
                return candidates[:top_k]

        return []

    async def get_process_node(self, process_node_id: str) -> Optional[Dict[str, Any]]:
        """Get a process node from Neo4j by id."""
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(
                "MATCH (p:Process {id: $id}) RETURN p",
                id=process_node_id,
            )
            record = await result.single()
            if not record:
                return None
            node = record["p"]
            return dict(node._properties)

    async def write_process_node(self, process_id: str, process_data: Dict[str, Any]):
        """Write or update a process node in Neo4j (merge by id).

        If process_data contains 'name' or 'definition', we compute and store embedding.
        """
        name = process_data.get("name") or ""
        definition = process_data.get("definition") or ""
        emb_text = f"{name}. {definition}".strip()
        embedding_vec = None
        try:
            emb = await self.embedding.embed([emb_text])
            embedding_vec = emb[0].tolist() if hasattr(emb[0], "tolist") else list(emb[0])
        except Exception:
            embedding_vec = None

        data_to_set = dict(process_data)
        if embedding_vec is not None:
            data_to_set["embedding"] = embedding_vec

        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            await session.run(
                "MERGE (p:Process {id: $id}) SET p += $data RETURN p",
                id=process_id,
                data=data_to_set,
            )

    async def sync_model(self, process_model_id: str, model_json: Dict[str, Any], enrichment_text: str = "") -> Dict[str, Any]:
        """High-level sync: extract entities via LLM, resolve & merge into the graph.

        Returns a report with merged counts and low-confidence candidates.
        """
        # 1) Ask LLM to extract entities and relations in strict JSON
        system_prompt = _build_extraction_system_prompt()
        user_content = json.dumps({"model_json": model_json, "enrichment_text": enrichment_text}, ensure_ascii=False)

        try:
            llm_output = await llm_service.complete(
                messages=[{"role": "user", "content": user_content}],
                system_prompt=system_prompt,
                max_tokens=2000,
                json_mode=True,
            )
        except Exception as e:
            return {"status": "error", "error": f"LLM extraction failed: {e}"}

        # parse JSON-only response
        try:
            extracted = json.loads(llm_output)
        except Exception as e:
            return {"status": "error", "error": f"Failed parsing LLM JSON output: {e}", "raw": llm_output}

        nodes = extracted.get("nodes", [])
        relationships = extracted.get("relationships", [])

        merged_counts = {}
        conflicts = []

        # 2) Merge nodes (resolve existing or create new)
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            tx = session
            for node in nodes:
                ntype = node.get("type")
                key = node.get("key") or {}
                props = node.get("properties") or {}

                # Build a canonical id if elementId present
                element_id = key.get("elementId") or key.get("id")
                if element_id:
                    # if elementId exists, prefer merging on elementId
                    # Try to find an existing node
                    res = await tx.run("MATCH (n:Process {elementId:$eid}) RETURN n", eid=element_id)
                    record = await res.single()
                    if record:
                        existing = record["n"]
                        node_id = existing._properties.get("id")
                        # update properties
                        update_params = {**props}
                        update_params["elementId"] = element_id
                        await tx.run("MATCH (n:Process {id:$id}) SET n += $data", id=node_id, data=update_params)
                        merged_counts[ntype] = merged_counts.get(ntype, 0) + 1
                        continue

                # try by provided id
                provided_id = key.get("id")
                if provided_id:
                    res = await tx.run("MATCH (n:Process {id:$id}) RETURN n", id=provided_id)
                    record = await res.single()
                    if record:
                        # update
                        await tx.run("MATCH (n:Process {id:$id}) SET n += $data", id=provided_id, data=props)
                        merged_counts[ntype] = merged_counts.get(ntype, 0) + 1
                        continue

                # try exact name + level match
                name = (props.get("name") or props.get("title") or key.get("name"))
                level = props.get("level")
                if name:
                    if level is not None:
                        res = await tx.run("MATCH (n:Process) WHERE n.name = $name AND n.level = $level RETURN n LIMIT 1", name=name, level=level)
                    else:
                        res = await tx.run("MATCH (n:Process) WHERE n.name = $name RETURN n LIMIT 1", name=name)
                    record = await res.single()
                    if record:
                        node_id = record["n"]._properties.get("id")
                        await tx.run("MATCH (n:Process {id:$id}) SET n += $data", id=node_id, data=props)
                        merged_counts[ntype] = merged_counts.get(ntype, 0) + 1
                        continue

                # fulltext candidates
                ft_query = name or list(props.values())[0:1]
                if isinstance(ft_query, list):
                    ft_query = " ".join(ft_query)
                ft_query = ft_query or ""
                if ft_query:
                    q = "CALL db.index.fulltext.queryNodes('processIndex', $query) YIELD node, score RETURN node, score ORDER BY score DESC LIMIT 5"
                    candidates = []
                    res = await tx.run(q, query=ft_query)
                    recs = await res.list()
                    for r in recs:
                        n = r[0]
                        sc = float(r[1])
                        candidates.append((dict(n._properties), sc))

                    # try embedding re-rank
                    chosen = None
                    confidence = 0.0
                    if candidates:
                        try:
                            texts = [f"{c[0].get('name','')}. {c[0].get('definition','')}" for c in candidates]
                            query_vec = await self.embedding.embed([ft_query])
                            cand_vecs = []
                            # use stored embeddings when available, else compute
                            for c in candidates:
                                emb = c[0].get("embedding")
                                if emb:
                                    cand_vecs.append(emb)
                                else:
                                    cand_vecs.append(None)

                            to_comp = []
                            idxs = []
                            for i, v in enumerate(cand_vecs):
                                if v is None:
                                    to_comp.append(texts[i])
                                    idxs.append(i)

                            if to_comp:
                                computed = await self.embedding.embed(to_comp)
                                computed_list = computed.tolist() if hasattr(computed, "tolist") else list(computed)
                                for ii, val in zip(idxs, computed_list):
                                    cand_vecs[ii] = val

                            qv = query_vec[0]
                            sims = [_cosine_similarity(qv, v) if v is not None else 0.0 for v in cand_vecs]
                            best_idx = int(max(range(len(sims)), key=lambda i: sims[i]))
                            confidence = sims[best_idx]
                            chosen = candidates[best_idx][0]
                        except Exception:
                            chosen = candidates[0][0]
                            confidence = 0.0

                    if chosen and confidence >= 0.75:
                        # merge into chosen
                        node_id = chosen.get("id")
                        # if chosen has no id, create one
                        if not node_id:
                            node_id = str(uuid.uuid4())
                            await tx.run("MATCH (n:Process {elementId:$eid}) SET n.id = $id", eid=chosen.get("elementId"), id=node_id)
                        # update properties
                        await tx.run("MATCH (n:Process {id:$id}) SET n += $data", id=node_id, data=props)
                        merged_counts[ntype] = merged_counts.get(ntype, 0) + 1
                        continue

                # otherwise create a new node
                new_id = str(uuid.uuid4())
                create_props = {**props, "id": new_id}
                # fallback label: Process for now
                await tx.run("CREATE (n:Process $data) RETURN n", data=create_props)
                merged_counts[ntype] = merged_counts.get(ntype, 0) + 1

        # 3) Merge relationships
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            for rel in relationships:
                # each rel: {from: {type, key}, to: {...}, type: "..."}
                from_node = rel.get("from") or {}
                to_node = rel.get("to") or {}
                rtype = rel.get("type")

                # resolve ids for endpoints using simple name matching
                from_id = await self._find_node_id(session, from_node)
                to_id = await self._find_node_id(session, to_node)

                if from_id and to_id:
                    await session.run(
                        "MATCH (a {id:$aid}), (b {id:$bid}) MERGE (a)-[r:%s]->(b) RETURN r" % rtype,
                        aid=from_id,
                        bid=to_id,
                    )

        return {"status": "ok", "merged_nodes": merged_counts, "conflicts": conflicts}

    async def _find_node_id(self, session, node_descriptor: Dict[str, Any]) -> Optional[str]:
        """Resolve a node descriptor to an existing node id using elementId, id, or name."""
        if not node_descriptor:
            return None
        key = node_descriptor.get("key") or {}
        props = node_descriptor.get("properties") or {}

        element_id = key.get("elementId") or props.get("elementId")
        if element_id:
            res = await session.run("MATCH (n {elementId:$eid}) RETURN n LIMIT 1", eid=element_id)
            rec = await res.single()
            if rec:
                return rec["n"]._properties.get("id")

        provided_id = key.get("id") or props.get("id")
        if provided_id:
            res = await session.run("MATCH (n {id:$id}) RETURN n LIMIT 1", id=provided_id)
            rec = await res.single()
            if rec:
                return rec["n"]._properties.get("id")

        name = key.get("name") or props.get("name")
        if name:
            res = await session.run("MATCH (n {name:$name}) RETURN n LIMIT 1", name=name)
            rec = await res.single()
            if rec:
                return rec["n"]._properties.get("id")

        return None


# Helper functions
def _cosine_similarity(a, b) -> float:
    try:
        dot = sum(x * y for x, y in zip(a, b))
        norma = math.sqrt(sum(x * x for x in a))
        normb = math.sqrt(sum(y * y for y in b))
        if norma == 0 or normb == 0:
            return 0.0
        return dot / (norma * normb)
    except Exception:
        return 0.0


def _build_extraction_system_prompt() -> str:
    """Return a schema-first system prompt instructing the LLM to output strict JSON.

    The prompt lists node types and relationship types and enforces JSON-only output.
    """
    prompt = """
You are a JSON-only extractor. Given a BPMN model JSON and optional enrichment_text, extract all entities that match the following schema and return a single JSON object and nothing else (no explanation):

Schema:
- nodes: array of { type: string, key: object, properties: object }
  Allowed node types: Process, DataObject, Actor, System, Rule, Definition, Level
  Key: unique identifier such as elementId or id or name.
  Properties: any additional properties (name, definition, level, actor_type, etc.)

- relationships: array of { from: {type, key}, to: {type, key}, type: string }
  Allowed relationship types: HAS_CHILD, CONTAINS, INPUT_OF, HAS_OUTPUT, DOING, TRIGGERS, SUBPROCESS_OF, COVERS, OUTPUTS, INPUT_TO_SYSTEM, USED_IN

Requirements:
1) Output must be valid JSON only (first and only token must be an object literal). Do not add any commentary.
2) Use the model_json and enrichment_text to find entities. Provide elementId when available.
3) Do not use regex or heuristics in your response — provide structured nodes and relationships only.
4) If uncertain about which existing Process (level 4) a description maps to, still include the candidate Process node with minimal properties; the service will ask for confirmation when merging.

Return example:
{
  "nodes": [
    {"type":"Process", "key":{"elementId":"10015"}, "properties":{"name":"Order Processing","level":4,"definition":"..."}},
    {"type":"DataObject","key":{"name":"Order form"},"properties":{"description":"..."}}
  ],
  "relationships": [
    {"from":{"type":"DataObject","key":{"name":"Order form"}}, "to":{"type":"Process","key":{"elementId":"10015"}}, "type":"INPUT_OF"}
  ]
}
"""
    return prompt
