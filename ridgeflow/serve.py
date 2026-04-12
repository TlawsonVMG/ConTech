import os

from waitress import serve

from ridgeflow import create_app

app = create_app()


if __name__ == "__main__":
    serve(app, host=os.getenv("RIDGEFLOW_DEV_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5051")))
