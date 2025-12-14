from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]


settings = Settings(
    cors_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]
)

