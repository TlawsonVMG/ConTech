import os

from ridgeflow import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("RIDGEFLOW_DEV_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5051")),
        debug=app.config.get("RIDGEFLOW_ENV") != "production",
    )
