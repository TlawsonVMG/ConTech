import os

from contech import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("CONTECH_DEV_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=app.config.get("CONTECH_ENV") != "production",
    )
