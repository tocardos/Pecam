from app.main import app

if __name__ == "__main__":
    #app.run(debug=False)
    app.run(host='0.0.0.0', port=5000, debug=False)