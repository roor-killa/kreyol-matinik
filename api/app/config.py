from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_db: str = "langmatinitje"
    postgres_user: str = "creole"
    postgres_password: str = "changeme"
    postgres_host: str = "db"
    postgres_port: int = 5432

    api_key: str = "changeme"
    api_port: int = 8000

    # JWT (variable d'env : JWT_SECRET)
    jwt_secret: str = "changeme-jwt-secret-at-least-32-chars!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 jours

    # Scraping automatique
    auto_scrape_hour: int = 3    # heure UTC du déclenchement quotidien
    whisper_model: str = "base"  # tiny | base | small | medium

    model_config = SettingsConfigDict(
        # Try multiple locations: Docker WORKDIR /app, running from api/, from kreyol-matinik/
        env_file=("../../.env", "../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
