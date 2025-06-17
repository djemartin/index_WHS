from flask import Flask, render_template, request, redirect, url_for
from tinydb import TinyDB, Query
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'db.json')
db = TinyDB(DB_PATH)

tours_table = db.table('tours')
scores_table = db.table('scores')

@app.route('/')
def index():
    return render_template('index.html', tours=tours_table.all())

@app.route('/add_tour', methods=['GET', 'POST'])
def add_tour():
    if request.method == 'POST':
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        tour = {
            'name': request.form.get('name'),
            'golf': request.form.get('golf'),
            'par': request.form.get('par', type=int),
            'slope': request.form.get('slope', type=int),
            'sss': request.form.get('sss', type=int),
            'pars': pars,
        }
        tours_table.insert(tour)
        return redirect(url_for('index'))
    return render_template('add_tour.html')

@app.route('/add_score/<int:tour_id>', methods=['GET', 'POST'])
def add_score(tour_id):
    tour = tours_table.get(doc_id=tour_id)
    if not tour:
        return redirect(url_for('index'))
    if request.method == 'POST':
        holes = []
        for i in range(1, 19):
            holes.append({
                'strokes': request.form.get(f'strokes_{i}', type=int),
                'fairway': bool(request.form.get(f'fairway_{i}')),
                'gir': bool(request.form.get(f'gir_{i}')),
                'putts': request.form.get(f'putts_{i}', type=int),
                'strokes_given': request.form.get(f'given_{i}', type=int)
            })
        score = {
            'tour_id': tour_id,
            'holes': holes
        }
        scores_table.insert(score)
        return redirect(url_for('index'))
    if 'pars' not in tour:
        tour['pars'] = [4] * 18
    return render_template('add_score.html', tour=tour)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
