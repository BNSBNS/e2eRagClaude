# app/services/rag/graph.py
from typing import List, Dict
from neo4j import GraphDatabase
from langchain.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain.llms import OpenAI

class GraphRAG:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
        self.graph = Neo4jGraph(
            url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        self.qa_chain = GraphCypherQAChain.from_llm(
            OpenAI(temperature=0),
            graph=self.graph,
            verbose=True
        )
    
    async def build_knowledge_graph(self, document_id: str, content: str):
        # Extract entities and relationships
        entities = await self.extract_entities(content)
        
        # Create nodes and relationships in Neo4j
        with self.driver.session() as session:
            for entity in entities:
                session.run("""
                    MERGE (e:Entity {name: $name, type: $type})
                    SET e.document_id = $doc_id
                """, name=entity["name"], type=entity["type"], doc_id=document_id)
            
            # Create relationships
            for rel in entities.get("relationships", []):
                session.run("""
                    MATCH (a:Entity {name: $source})
                    MATCH (b:Entity {name: $target})
                    MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                """, source=rel["source"], target=rel["target"], rel_type=rel["type"])
    
    async def query(self, question: str, user_id: str) -> Dict:
        # Query the knowledge graph
        response = self.qa_chain.run(question)
        
        return {
            "answer": response.get("result", ""),
            "cypher_query": response.get("query", ""),
            "method": "graph_rag"
        }