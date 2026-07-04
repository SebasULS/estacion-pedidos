from app import create_app

# Vercel detecta `app` automáticamente cuando se usa @vercel/python.
app = create_app()
