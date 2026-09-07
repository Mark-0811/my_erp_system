from core import create_app, initialize_database


app = create_app()


if __name__ == "__main__":
    initialize_database(app)
    app.run(debug=True)
