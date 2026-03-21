"""Flask app runner"""

from main import app

port: int = 5002

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=port)
