from flask import Flask, Response, jsonify, render_template, request
from config import Config
from db import init_db
from service import dashboard_data, export_csv_text, get_update_status, start_update

app = Flask(__name__)

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/api/dashboard')
def api_dashboard():
    return jsonify(dashboard_data())

@app.post('/api/update')
def api_update():
    return jsonify(start_update())

@app.get('/api/update/status')
def api_update_status():
    run_id = request.args.get('run_id', type=int)
    row = get_update_status(run_id)
    return jsonify({'ok': bool(row), 'run': row})

@app.get('/api/export.csv')
def export_csv():
    return Response(export_csv_text(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=bojnurd_apartments.csv'})

@app.get('/api/health')
def health():
    return jsonify({'ok': True, 'source': 'divar-live', 'city': Config.CITY_NAME})

if __name__ == '__main__':
    init_db()
    print(f'Bojnurd Property Analytics → http://{Config.HOST}:{Config.PORT}')
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
