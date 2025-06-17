from flask import Flask, render_template, request, redirect, url_for
from tinydb import TinyDB, Query
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'db.json')
db = TinyDB(DB_PATH)

tours_table = db.table('tours')
scores_table = db.table('scores')
golfs_table = db.table('golfs')

@app.route('/')
def index():
    golfs = {g.doc_id: g for g in golfs_table.all()}
    return render_template('index.html', tours=tours_table.all(), golfs=golfs)

@app.route('/golf', methods=['GET', 'POST'])
def manage_golf():
    """Create or update a golf and display the list of existing ones."""
    golf_id = request.args.get('id', type=int)
    if request.method == 'POST':
        form_id = request.form.get('id', type=int)
        data = {
            'name': request.form.get('name'),
            'course': request.form.get('course'),
            'par': request.form.get('par', type=int),
            'tees': request.form.get('tees'),
            'slope': request.form.get('slope', type=int),
            'sss': request.form.get('sss', type=int)
        }
        if form_id:
            golfs_table.update(data, doc_ids=[form_id])
        else:
            golfs_table.insert(data)
        return redirect(url_for('manage_golf'))

    golf = golfs_table.get(doc_id=golf_id) if golf_id else None
    golfs = golfs_table.all()
    return render_template('golf_form.html', golf=golf, golfs=golfs)


@app.route('/golf/delete/<int:golf_id>', methods=['POST'])
def delete_golf(golf_id):
    """Delete a golf from the database."""
    golfs_table.remove(doc_ids=[golf_id])
    return redirect(url_for('manage_golf'))

@app.route('/add_tour', methods=['GET', 'POST'])
def add_tour():
    if request.method == 'POST':
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        tour = {
            'name': request.form.get('name'),
            'golf_id': request.form.get('golf', type=int),
            'par': request.form.get('par', type=int),
            'slope': request.form.get('slope', type=int),
            'sss': request.form.get('sss', type=int),
            'pars': pars,
        }
        tours_table.insert(tour)
        return redirect(url_for('index'))
    golfs = golfs_table.all()
    # Include doc_id in JSON data so the client side can easily
    # look up additional information for a selected course
    golfs_json = []
    for g in golfs:
        data = dict(g)
        data['doc_id'] = g.doc_id
        golfs_json.append(data)
    return render_template('add_tour.html', golfs=golfs, golfs_json=golfs_json)

@app.route('/add_score/<int:tour_id>', methods=['GET', 'POST'])
def add_score(tour_id):
    tour = tours_table.get(doc_id=tour_id)
    if not tour:
        return redirect(url_for('index'))
    if request.method == 'POST':
        holes = []
        for i in range(1, 19):
            par = request.form.get(f'par_{i}', type=int)
            hole = {
                'par': par,
                'strokes': request.form.get(f'strokes_{i}', type=int),
                'fairway': bool(request.form.get(f'fairway_{i}')),
                'gir': bool(request.form.get(f'gir_{i}')),
                'putts': request.form.get(f'putts_{i}', type=int),
                'strokes_given': request.form.get(f'given_{i}', type=int)
            }
            holes.append(hole)
        score = {
            'tour_id': tour_id,
            'holes': holes
        }
        scores_table.insert(score)

        fairway_possible = sum(1 for h in holes if h['par'] != 3)
        fairway_hits = sum(1 for h in holes if h['par'] != 3 and h['fairway'])
        gir_hits = sum(1 for h in holes if h['gir'])
        total_putts = sum(h['putts'] for h in holes)
        avg_putts = format(total_putts / 18, '.1f')

        stats = {
            'fairway': f"{fairway_hits}/{fairway_possible}",
            'putts_total': total_putts,
            'putts_avg': avg_putts,
            'gir': f"{gir_hits}/18"
        }

        return render_template('score_summary.html', stats=stats)
    if 'pars' not in tour:
        tour['pars'] = [4] * 18
    return render_template('add_score.html', tour=tour)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
