from flask import Flask, render_template, request, redirect, url_for
from tinydb import TinyDB, Query
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'db.json')
db = TinyDB(DB_PATH)

tours_table = db.table('tours')
scores_table = db.table('scores')
stats_table = db.table('stats')
golfs_table = db.table('golfs')

# Ensure existing tours have a PCC value for backward compatibility
for t in tours_table.all():
    if 'pcc' not in t:
        tours_table.update({'pcc': 0}, doc_ids=[t.doc_id])


def distribute_handicap(handicap, hcps):
    """Return a list with strokes received for each hole."""
    if handicap is None:
        handicap = 0
    base = handicap // 18
    extra = handicap % 18
    distribution = [base] * 18
    for i, hcp in enumerate(hcps):
        if hcp <= extra:
            distribution[i] += 1
    return distribution


def calculate_sba(pars, strokes, handicap, hcps):
    """Compute SBA values and strokes received per hole."""
    given = distribute_handicap(handicap, hcps)
    adjusted = []
    for p, s, g in zip(pars, strokes, given):
        limit = p + 2 + g
        adjusted.append(min(s, limit))
    total_sba = sum(adjusted)
    return total_sba, adjusted, given


def diff_whs(sba_total, slope, sss, pcc=0):
    """Calculate the WHS differential for a card.

    The PCC value is always subtracted from the differential, so a PCC of
    ``+1`` will decrease the differential by 1 and a PCC of ``-1`` will
    increase it by 1. The result is rounded **down** to the nearest tenth as
    requested.
    """

    import math

    diff = ((113 / slope) * (sba_total - sss) - pcc)
    # Round down to the nearest tenth (e.g. 19.29 -> 19.2)
    return math.floor(diff * 10) / 10

@app.route('/')
def index():
    golfs = {g.doc_id: g for g in golfs_table.all()}
    all_scores = scores_table.all()
    scores = {s['tour_id']: s for s in all_scores}

    # Determine the 8 lowest Diff WHS among the last 20 scorecards
    recent_scores = sorted(all_scores, key=lambda x: x.doc_id, reverse=True)[:20]
    diffs = []
    for s in recent_scores:
        holes = s.get('holes', [])
        total_sba = sum(
            (h.get('adjusted') if h.get('adjusted') is not None else 0)
            for h in holes
        )
        total_sba_val = float(total_sba)
        tour = tours_table.get(doc_id=s.get('tour_id'))
        if not tour:
            continue
        slope = tour.get('slope')
        sss = tour.get('sss')
        pcc = tour.get('pcc', 0)
        if slope and sss is not None:
            diff = diff_whs(total_sba_val, slope, sss, pcc)
            diffs.append((diff, s.get('tour_id')))

    best_diff_ids = set()
    new_index = None
    if diffs:
        diffs.sort(key=lambda x: x[0])
        best_diff_ids = {tid for _, tid in diffs[:8]}
        if len(diffs) >= 8:
            best = [d[0] for d in diffs[:8]]
            new_index = round(sum(best) / 8, 1)
    tours = []
    # Sort tours by date descending so the most recent competition
    # appears first on the main page
    for idx, t in enumerate(
        sorted(tours_table.all(), key=lambda x: x.get('date', ''), reverse=True),
        start=1,
    ):
        score_entry = scores.get(t.doc_id)
        total_score = None
        total_sba = None
        if score_entry:
            holes = score_entry.get('holes', [])
            total_score = sum(h.get('strokes', 0) for h in holes)
            total_sba = sum(
                (h.get('adjusted') if h.get('adjusted') is not None else 0)
                for h in holes
            )
            total_sba_val = float(total_sba)
            slope = t.get('slope')
            sss = t.get('sss')
            pcc = t.get('pcc', 0)
            if slope and sss is not None:
                diff_value = diff_whs(total_sba_val, slope, sss, pcc)
                diff_whs_val = diff_value
            else:
                diff_whs_val = None
            formatted_sba = int(total_sba)
        else:
            diff_whs_val = None
            formatted_sba = None
        tour_data = dict(t)
        tour_data['doc_id'] = t.doc_id
        tour_data['total_score'] = total_score
        tour_data['total_sba'] = (
            formatted_sba if formatted_sba is not None else None
        )
        tour_data['diff_whs'] = diff_whs_val
        tour_data['highlight_diff'] = t.doc_id in best_diff_ids
        tour_data['has_score'] = score_entry is not None
        if idx <= 20:
            tour_data['recent_no'] = idx
        else:
            tour_data['recent_no'] = None
        tours.append(tour_data)
    return render_template('index.html', tours=tours, golfs=golfs, new_index=new_index)

@app.route('/start_score', methods=['GET', 'POST'])
def start_score():
    """Create a tour with default par data and go directly to score entry."""
    if request.method == 'POST':
        golf_id = request.form.get('golf', type=int)
        name = request.form.get('name')
        jour = request.form.get('jour', type=int)
        date = request.form.get('date')
        pcc = request.form.get('pcc', type=int)
        if pcc is None:
            pcc = 0
        golf = golfs_table.get(doc_id=golf_id)
        if golf:
            pars = golf.get('pars', [4] * 18)
            hcps = golf.get('hcps', list(range(1, 19)))
            tour = {
                'name': name,
                'jour': jour,
                'date': date,
                'golf_id': golf_id,
                'par': golf.get('par'),
                'slope': golf.get('slope'),
                'sss': golf.get('sss'),
                'pcc': pcc,
                'pars': pars,
                'hcps': hcps,
            }
            tour_id = tours_table.insert(tour)
            return redirect(url_for('add_score', tour_id=tour_id))
    golfs = golfs_table.all()
    return render_template('start_score.html', golfs=golfs)

@app.route('/golf', methods=['GET', 'POST'])
def manage_golf():
    """Create or update a golf and display the list of existing ones."""
    golf_id = request.args.get('id', type=int)
    if request.method == 'POST':
        form_id = request.form.get('id', type=int)
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        hcps = [request.form.get(f'hcp_{i}', type=int) for i in range(1, 19)]
        data = {
            'name': request.form.get('name'),
            'course': request.form.get('course'),
            'par': request.form.get('par', type=int),
            'tees': request.form.get('tees'),
            'slope': request.form.get('slope', type=int),
            'sss': request.form.get('sss', type=float),
            'pars': pars,
            'hcps': hcps,
        }
        if form_id:
            golfs_table.update(data, doc_ids=[form_id])
        else:
            golfs_table.insert(data)
        return redirect(url_for('manage_golf'))

    golf = golfs_table.get(doc_id=golf_id) if golf_id else None
    if golf and 'pars' not in golf:
        golf['pars'] = [4] * 18
    if golf and 'hcps' not in golf:
        golf['hcps'] = list(range(1, 19))
    golfs = golfs_table.all()
    return render_template('golf_form.html', golf=golf, golfs=golfs)


@app.route('/golf/delete/<int:golf_id>', methods=['POST'])
def delete_golf(golf_id):
    """Delete a golf from the database."""
    golfs_table.remove(doc_ids=[golf_id])
    return redirect(url_for('manage_golf'))

@app.route('/add_tour', methods=['GET', 'POST'])
def add_tour():
    """Create or update a tour."""
    tour_id = request.args.get('id', type=int)
    if request.method == 'POST':
        form_id = request.form.get('id', type=int)
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        hcps = [request.form.get(f'hcp_{i}', type=int) for i in range(1, 19)]
        pcc_val = request.form.get('pcc', type=int)
        if pcc_val is None:
            pcc_val = 0
        tour = {
            'name': request.form.get('name'),
            'jour': request.form.get('jour', type=int),
            'date': request.form.get('date'),
            'golf_id': request.form.get('golf', type=int),
            'par': request.form.get('par', type=int),
            'slope': request.form.get('slope', type=int),
            'sss': request.form.get('sss', type=float),
            'pcc': pcc_val,
            'pars': pars,
            'hcps': hcps,
        }
        if form_id:
            tours_table.update(tour, doc_ids=[form_id])
        else:
            tours_table.insert(tour)
        return redirect(url_for('index'))

    tour = tours_table.get(doc_id=tour_id) if tour_id else None
    if tour and 'hcps' not in tour:
        tour['hcps'] = list(range(1, 19))
    golfs = golfs_table.all()
    # Include doc_id in JSON data so the client side can easily
    # look up additional information for a selected course
    golfs_json = []
    for g in golfs:
        data = dict(g)
        if 'pars' not in data:
            data['pars'] = [4] * 18
        if 'hcps' not in data:
            data['hcps'] = list(range(1, 19))
        data['doc_id'] = g.doc_id
        golfs_json.append(data)
    return render_template('add_tour.html', tour=tour, golfs=golfs, golfs_json=golfs_json)


@app.route('/tour/delete/<int:tour_id>', methods=['POST'])
def delete_tour(tour_id):
    """Delete a tour from the database."""
    tours_table.remove(doc_ids=[tour_id])
    return redirect(url_for('index'))

@app.route('/add_score/<int:tour_id>', methods=['GET', 'POST'])
def add_score(tour_id):
    tour = tours_table.get(doc_id=tour_id)
    if not tour:
        return redirect(url_for('index'))
    # Retrieve existing score for this tour if any
    Score = Query()
    existing_score = scores_table.get(Score.tour_id == tour_id)
    if request.method == 'POST':
        # Allow updating the PCC value when submitting the score form
        pcc_val = request.form.get('pcc', type=int)
        if pcc_val is None:
            pcc_val = 0
        tours_table.update({'pcc': pcc_val}, doc_ids=[tour_id])
        tour['pcc'] = pcc_val

        handicap = request.form.get('handicap', type=int)
        hcps = tour.get('hcps', list(range(1, 19)))
        given_dist = distribute_handicap(handicap, hcps)
        holes = []
        for i in range(1, 19):
            par = request.form.get(f'par_{i}', type=int)
            strokes = request.form.get(f'strokes_{i}', type=int)
            given = given_dist[i-1]
            limit = par + 2 + given
            adjusted = min(strokes, limit) if strokes is not None else None
            hole = {
                'par': par,
                'strokes_given': given,
                'strokes': strokes,
                'adjusted': adjusted,
                'fairway': bool(request.form.get(f'fairway_{i}')),
                'gir': bool(request.form.get(f'gir_{i}')),
                'putts': request.form.get(f'putts_{i}', type=int)
            }
            holes.append(hole)
        score = {
            'tour_id': tour_id,
            'handicap': handicap,
            'holes': holes
        }
        # Insert or update the score so data is persisted
        if existing_score:
            scores_table.update(score, doc_ids=[existing_score.doc_id])
            score_id = existing_score.doc_id
        else:
            score_id = scores_table.insert(score)

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

        # Compute WHS differential for this card
        slope = tour.get('slope')
        sss = tour.get('sss')
        pcc = tour.get('pcc', 0)
        if slope and sss is not None:
            diff_value = diff_whs(sum(h['adjusted'] for h in holes), slope, sss, pcc)
            stats['diff_whs'] = format(diff_value, '.1f')

        # Persist stats in dedicated table
        stats_data = {
            'score_id': score_id,
            'tour_id': tour_id,
            'fairway_hits': fairway_hits,
            'fairway_possible': fairway_possible,
            'gir_hits': gir_hits,
            'putts_total': total_putts,
            'putts_avg': avg_putts,
        }
        Stats = Query()
        existing_stats = stats_table.get(Stats.score_id == score_id)
        if existing_stats:
            stats_table.update(stats_data, doc_ids=[existing_stats.doc_id])
        else:
            stats_table.insert(stats_data)

        # Calculate average putts per card across all recorded cards
        stats_entries = stats_table.all()
        num_cards_overall = len(stats_entries)
        if num_cards_overall:
            avg_putts_cards = sum(s.get('putts_total', 0) / 18 for s in stats_entries) / num_cards_overall
            stats['putts_avg_cards'] = format(avg_putts_cards, '.1f')
        else:
            stats['putts_avg_cards'] = '0.0'

        return render_template('score_summary.html', stats=stats)
    if 'pars' not in tour:
        tour['pars'] = [4] * 18
    if 'hcps' not in tour:
        tour['hcps'] = list(range(1, 19))
    return render_template('add_score.html', tour=tour, score=existing_score)


@app.route('/scores')
def list_scores():
    """Display the list of recorded scorecards."""
    current_index = request.args.get('index', type=float)
    sort_key = request.args.get('sort', 'date')

    golfs = {g.doc_id: g for g in golfs_table.all()}
    tours = {t.doc_id: t for t in tours_table.all()}
    cards = []
    for s in scores_table.all():
        tour = tours.get(s.get('tour_id'))
        if not tour:
            continue
        holes = s.get('holes', [])
        total_score = sum(h.get('strokes', 0) for h in holes)
        total_sba = sum(
            (h.get('adjusted') if h.get('adjusted') is not None else 0)
            for h in holes
        )
        pcc = tour.get('pcc', 0)
        slope = tour.get('slope')
        sss = tour.get('sss')
        diff = None
        emoji = ''
        if slope and sss is not None:
            diff_value = diff_whs(total_sba, slope, sss, pcc)
            diff = diff_value
            if current_index is not None:
                if diff < current_index:
                    emoji = '🔻'
                elif diff > current_index:
                    emoji = '🔺'
                else:
                    emoji = '➡️'
        cards.append({
            'tour': tour,
            'golf': golfs.get(tour.get('golf_id')),
            'total_score': total_score,
            'total_sba': int(total_sba),
            'diff': diff,
            'emoji': emoji,
        })

    if sort_key == 'diff':
        cards.sort(key=lambda x: (x['diff'] is None, x.get('diff')))
    else:
        cards.sort(key=lambda x: x['tour'].get('date', ''))

    return render_template('scores_list.html', cards=cards, current_index=current_index, sort=sort_key)


@app.route('/stats')
def overall_stats():
    """Display aggregate statistics for all scorecards."""
    stats_entries = stats_table.all()
    score_entries = scores_table.all()

    num_cards = len(stats_entries)

    total_putts = sum(s.get('putts_total', 0) for s in stats_entries)
    total_fairway_hits = sum(s.get('fairway_hits', 0) for s in stats_entries)
    total_fairway_possible = sum(s.get('fairway_possible', 0) for s in stats_entries)
    total_gir_hits = sum(s.get('gir_hits', 0) for s in stats_entries)

    total_scores = 0
    total_sba = 0
    for s in score_entries:
        holes = s.get('holes', [])
        # Total score for the current card
        card_score_total = sum(h.get('strokes', 0) for h in holes)
        total_scores += card_score_total

        # Total SBA for the current card
        card_sba_total = sum(
            (h.get('adjusted') if h.get('adjusted') is not None else 0)
            for h in holes
        )
        total_sba += card_sba_total

    avg_putts = format(total_putts / num_cards, '.1f') if num_cards else '0.0'
    avg_putts_cards = (
        format(total_putts / (num_cards * 18), '.1f') if num_cards else '0.0'
    )
    avg_score = format(total_scores / num_cards, '.1f') if num_cards else '0.0'
    avg_fairways = format(total_fairway_hits / num_cards, '.1f') if num_cards else '0.0'
    # Average SBA per card
    avg_sba = format(total_sba / num_cards, '.1f') if num_cards else '0.0'

    # Average number of strokes per card
    avg_nb_coups = format(total_scores / num_cards, '.1f') if num_cards else '0.0'

    fairway_pct = (
        format(total_fairway_hits / total_fairway_possible * 100, '.1f')
        if total_fairway_possible else '0.0'
    )
    gir_possible = num_cards * 18
    gir_pct = (
        format(total_gir_hits / gir_possible * 100, '.1f')
        if gir_possible else '0.0'
    )

    stats = {
        'avg_putts': avg_putts,
        'avg_putts_cards': avg_putts_cards,
        'avg_score': avg_score,
        'avg_fairways': avg_fairways,
        'fairway_pct': fairway_pct,
        'gir_pct': gir_pct,
        'avg_sba': avg_sba,
        'avg_nb_coups': avg_nb_coups,
    }
    return render_template('stats_overall.html', stats=stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
