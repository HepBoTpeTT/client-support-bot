from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):
    # MySQL connection
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_root_password: str = ""
    mysql_database: str = "site_assistant"

    # App
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    public_base_url: str = "http://localhost:8000"

    # Proxy (optional, for OpenAI access)
    openai_proxy: str = ""

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Embedding model
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()