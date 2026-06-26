"""Configuration management for BPMN Agent system."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    API_TITLE: str = "BPMN Agent API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LLM Provider (Module 7)
    LLM_PROVIDER_URL: str = "https://api.avalai.ir/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2000
    
    # MariaDB (Module 8 - Short-term Memory)
    MARIADB_HOST: str = "localhost"
    MARIADB_PORT: int = 3306
    MARIADB_USER: str = "root"
    MARIADB_PASSWORD: str = ""
    MARIADB_DATABASE: str = "bpmn_agent"
    SQLALCHEMY_DATABASE_URL: Optional[str] = None
    
    # Neo4j (Module 9 - Semantic Memory)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    
    # Embedding Service (Module 12)
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 384
    USE_LOCAL_EMBEDDING: bool = True
    EMBEDDING_API_URL: Optional[str] = None
    
    # SVG Render Service (Module 10) - External
    SVG_SERVICE_URL: str = "http://localhost:8001/render"
    
    # Selection Box Service (Module 11) - External
    SELECTION_BOX_SERVICE_URL: str = "http://localhost:8002/selection"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_database_url(self) -> str:
        """Construct database URL from components."""
        if self.SQLALCHEMY_DATABASE_URL:
            return self.SQLALCHEMY_DATABASE_URL
        return f"mysql+mysqlconnector://{self.MARIADB_USER}:{self.MARIADB_PASSWORD}@{self.MARIADB_HOST}:{self.MARIADB_PORT}/{self.MARIADB_DATABASE}"


settings = Settings()
