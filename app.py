from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
import csv
import os

from config import Config
from models import db, User, Golf, Tour, Score, Stats
from forms import LoginForm, GolfForm, TourForm

app = Flask(__name__)
app.config.from_object(Config)

# Extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def migrate_from_tinydb():
    """Import data from TinyDB if the new database is empty."""
    from tinydb import TinyDB

    db_path = os.path.join(os.path.dirname(__file__), 'db.json')
    if not os.path.exists(db_path) or Tour.query.first():
        return

    tdb = TinyDB(db_path)
    for g in tdb.table('golfs').all():
        golf = Golf(id=g.doc_id, name=g.get('name'), course=g.get('course'), par=g.get('par'),
                    slope=g.get('slope'), sss=g.get('sss'), tees=g.get('tees'),
                    pars=g.get('pars'), hcps=g.get('hcps'))
        db.session.merge(golf)
    for t in tdb.table('tours').all():
        tour = Tour(id=t.doc_id, name=t.get('name'), jour=t.get('jour'), date=t.get('date'),
                    golf_id=t.get('golf_id'), par=t.get('par'), slope=t.get('slope'),
                    sss=t.get('sss'), pcc=t.get('pcc', 0), pars=t.get('pars'), hcps=t.get('hcps'))
        db.session.merge(tour)
    for s in tdb.table('scores').all():
        score = Score(id=s.doc_id, tour_id=s.get('tour_id'), handicap=s.get('handicap'), holes=s.get('holes'))
        db.session.merge(score)
    for st in tdb.table('stats').all():
        stats = Stats(id=st.doc_id, score_id=st.get('score_id'), tour_id=st.get('tour_id'),
                      fairway_hits=st.get('fairway_hits'), fairway_possible=st.get('fairway_possible'),
                      gir_hits=st.get('gir_hits'), putts_total=st.get('putts_total'), putts_avg=st.get('putts_avg'))
        db.session.merge(stats)
    db.session.commit()


# Utility functions

def distribute_handicap(handicap, hcps):
    if handicap is None:
        handicap = 0
    base = handicap // 18
    extra = handicap % 18
    dist = [base] * 18
    for i, h in enumerate(hcps):
        if h <= extra:
            dist[i] += 1
    return dist


def diff_whs(sba_total, slope, sss, pcc=0):
    import math
    diff = (113 / slope) * (sba_total - sss) - pcc
    base = math.floor(diff * 10)
    rounded = base / 10
    centieme = int(abs(diff) * 100) % 10
    if centieme > 5:
        rounded += 0.1
    return round(rounded, 1)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            user = User(username=form.username.data)
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/')
@login_required
def index():
    golfs = {g.id: g for g in Golf.query.all()}
    all_scores = Score.query.all()
    scores = {s.tour_id: s for s in all_scores}
    recent = sorted(all_scores, key=lambda x: x.id, reverse=True)[:20]
    diffs = []
    for s in recent:
        holes = s.holes or []
        total_sba = sum(h.get('adjusted') or 0 for h in holes)
        tour = db.session.get(Tour, s.tour_id)
        if not tour:
            continue
        if tour.slope and tour.sss is not None:
            diffs.append((diff_whs(total_sba, tour.slope, tour.sss, tour.pcc), tour.id))
    best_diff_ids = set()
    new_index = None
    if diffs:
        diffs.sort(key=lambda x: x[0])
        best_diff_ids = {tid for _, tid in diffs[:8]}
        if len(diffs) >= 8:
            best = [d[0] for d in diffs[:8]]
            new_index = round(sum(best) / 8, 1)
    tours = []
    for idx, t in enumerate(Tour.query.order_by(Tour.date.desc()).all(), start=1):
        score = scores.get(t.id)
        total_score = None
        total_sba = None
        diff_val = None
        if score:
            holes = score.holes or []
            total_score = sum(h.get('strokes', 0) for h in holes)
            total_sba = sum(h.get('adjusted') or 0 for h in holes)
            if t.slope and t.sss is not None:
                diff_val = diff_whs(total_sba, t.slope, t.sss, t.pcc)
        tours.append({
            'doc_id': t.id,
            'name': t.name,
            'jour': t.jour,
            'date': t.date,
            'pcc': t.pcc,
            'golf_id': t.golf_id,
            'total_score': total_score,
            'total_sba': int(total_sba) if total_sba is not None else None,
            'diff_whs': diff_val,
            'highlight_diff': t.id in best_diff_ids,
            'has_score': score is not None,
            'recent_no': idx if idx <= 20 else None
        })
    return render_template('index.html', tours=tours, golfs=golfs, new_index=new_index)


@app.route('/golf', methods=['GET', 'POST'])
@login_required
def manage_golf():
    golf_id = request.args.get('id', type=int)
    form = GolfForm()
    if form.validate_on_submit():
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        hcps = [request.form.get(f'hcp_{i}', type=int) for i in range(1, 19)]
        if golf_id:
            golf = db.session.get(Golf, golf_id)
        else:
            golf = Golf()
        golf.name = form.name.data
        golf.course = form.course.data
        golf.par = form.par.data
        golf.tees = form.tees.data
        golf.slope = form.slope.data
        golf.sss = form.sss.data
        golf.pars = pars
        golf.hcps = hcps
        db.session.add(golf)
        db.session.commit()
        return redirect(url_for('manage_golf'))

    golf = db.session.get(Golf, golf_id) if golf_id else None
    if golf and not golf.pars:
        golf.pars = [4] * 18
    if golf and not golf.hcps:
        golf.hcps = list(range(1, 19))
    golfs = Golf.query.all()
    return render_template('golf_form.html', golf=golf, golfs=golfs)


@app.route('/golf/delete/<int:golf_id>', methods=['POST'])
@login_required
def delete_golf(golf_id):
    golf = db.session.get(Golf, golf_id)
    if golf:
        db.session.delete(golf)
        db.session.commit()
    return redirect(url_for('manage_golf'))


@app.route('/add_tour', methods=['GET', 'POST'])
@login_required
def add_tour():
    tour_id = request.args.get('id', type=int)
    form = TourForm()
    form.golf.choices = [(g.id, g.name) for g in Golf.query.all()]
    if form.validate_on_submit():
        pars = [request.form.get(f'par_{i}', type=int) for i in range(1, 19)]
        hcps = [request.form.get(f'hcp_{i}', type=int) for i in range(1, 19)]
        if tour_id:
            tour = db.session.get(Tour, tour_id)
        else:
            tour = Tour(user_id=current_user.id)
        tour.name = form.name.data
        tour.jour = form.jour.data
        tour.date = form.date.data.strftime('%Y-%m-%d')
        tour.golf_id = form.golf.data
        tour.par = form.par.data
        tour.slope = form.slope.data
        tour.sss = form.sss.data
        tour.pcc = form.pcc.data or 0
        tour.pars = pars
        tour.hcps = hcps
        db.session.add(tour)
        db.session.commit()
        return redirect(url_for('index'))

    tour = db.session.get(Tour, tour_id) if tour_id else None
    if tour and not tour.hcps:
        tour.hcps = list(range(1, 19))
    golfs = Golf.query.all()
    return render_template('add_tour.html', tour=tour, golfs=golfs, golfs_json=[{**g.__dict__, 'doc_id': g.id} for g in golfs])


@app.route('/tour/delete/<int:tour_id>', methods=['POST'])
@login_required
def delete_tour(tour_id):
    tour = db.session.get(Tour, tour_id)
    if tour:
        db.session.delete(tour)
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/start_score', methods=['GET', 'POST'])
@login_required
def start_score():
    if request.method == 'POST':
        golf_id = request.form.get('golf', type=int)
        name = request.form.get('name')
        jour = request.form.get('jour', type=int)
        date = request.form.get('date')
        pcc = request.form.get('pcc', type=int) or 0
        golf = db.session.get(Golf, golf_id)
        if golf:
            tour = Tour(name=name, jour=jour, date=date, golf_id=golf_id, par=golf.par,
                        slope=golf.slope, sss=golf.sss, pcc=pcc, pars=golf.pars,
                        hcps=golf.hcps, user_id=current_user.id)
            db.session.add(tour)
            db.session.commit()
            return redirect(url_for('add_score', tour_id=tour.id))
    golfs = Golf.query.all()
    return render_template('start_score.html', golfs=golfs)


@app.route('/add_score/<int:tour_id>', methods=['GET', 'POST'])
@login_required
def add_score(tour_id):
    tour = db.session.get(Tour, tour_id)
    if not tour:
        return redirect(url_for('index'))
    score = Score.query.filter_by(tour_id=tour_id).first()
    if request.method == 'POST':
        pcc_val = request.form.get('pcc', type=int) or 0
        tour.pcc = pcc_val
        handicap = request.form.get('handicap', type=int)
        hcps = tour.hcps or list(range(1, 19))
        given_dist = distribute_handicap(handicap, hcps)
        holes = []
        for i in range(1, 19):
            par = request.form.get(f'par_{i}', type=int)
            strokes = request.form.get(f'strokes_{i}', type=int)
            given = given_dist[i-1]
            limit = par + 2 + given
            adjusted_from_form = request.form.get(f'adjusted_{i}', type=int)
            if adjusted_from_form is not None and score:
                adjusted = adjusted_from_form
            else:
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
        if not score:
            score = Score(tour_id=tour_id)
        score.handicap = handicap
        score.holes = holes
        db.session.add(score)
        db.session.commit()

        fairway_possible = sum(1 for h in holes if h['par'] != 3)
        fairway_hits = sum(1 for h in holes if h['par'] != 3 and h['fairway'])
        gir_hits = sum(1 for h in holes if h['gir'])
        total_putts = sum(h['putts'] for h in holes)
        avg_putts = format(total_putts / 18, '.1f')
        stats = Stats.query.filter_by(score_id=score.id).first()
        if not stats:
            stats = Stats(score_id=score.id, tour_id=tour_id)
        stats.fairway_hits = fairway_hits
        stats.fairway_possible = fairway_possible
        stats.gir_hits = gir_hits
        stats.putts_total = total_putts
        stats.putts_avg = avg_putts
        db.session.add(stats)
        db.session.commit()

        diff_val = None
        if tour.slope and tour.sss is not None:
            diff_val = diff_whs(sum(h['adjusted'] for h in holes), tour.slope, tour.sss, tour.pcc)
        summary = {
            'fairway': f"{fairway_hits}/{fairway_possible}",
            'putts_total': total_putts,
            'putts_avg': avg_putts,
            'gir': f"{gir_hits}/18",
            'diff_whs': format(diff_val, '.1f') if diff_val is not None else None,
            'putts_avg_cards': format(sum(s.putts_total for s in Stats.query.all())/(len(Stats.query.all())*18), '.1f') if Stats.query.all() else '0.0'
        }
        return render_template('score_summary.html', stats=summary)

    if not tour.pars:
        tour.pars = [4] * 18
    if not tour.hcps:
        tour.hcps = list(range(1, 19))
    return render_template('add_score.html', tour=tour, score=score)


@app.route('/scores')
@login_required
def list_scores():
    current_index = request.args.get('index', type=float)
    sort_key = request.args.get('sort', 'date')
    golfs = {g.id: g for g in Golf.query.all()}
    tours = {t.id: t for t in Tour.query.all()}
    cards = []
    for s in Score.query.all():
        tour = tours.get(s.tour_id)
        if not tour:
            continue
        holes = s.holes or []
        total_score = sum(h.get('strokes', 0) for h in holes)
        total_sba = sum(h.get('adjusted') or 0 for h in holes)
        diff = None
        emoji = ''
        if tour.slope and tour.sss is not None:
            diff = diff_whs(total_sba, tour.slope, tour.sss, tour.pcc)
            if current_index is not None:
                if diff < current_index:
                    emoji = '🔻'
                elif diff > current_index:
                    emoji = '🔺'
                else:
                    emoji = '➡️'
        cards.append({
            'tour': tour,
            'golf': golfs.get(tour.golf_id),
            'total_score': total_score,
            'total_sba': int(total_sba),
            'diff': diff,
            'emoji': emoji,
        })
    if sort_key == 'diff':
        cards.sort(key=lambda x: (x['diff'] is None, x.get('diff')))
    else:
        cards.sort(key=lambda x: x['tour'].date or '')
    return render_template('scores_list.html', cards=cards, current_index=current_index, sort=sort_key)


@app.route('/export/csv')
@login_required
def export_csv():
    fp = os.path.join(app.instance_path, 'scores.csv')
    os.makedirs(app.instance_path, exist_ok=True)
    with open(fp, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Tour', 'Date', 'Total', 'SBA', 'Diff'])
        for s in Score.query.all():
            t = db.session.get(Tour, s.tour_id)
            holes = s.holes or []
            total_score = sum(h.get('strokes', 0) for h in holes)
            total_sba = sum(h.get('adjusted') or 0 for h in holes)
            diff = diff_whs(total_sba, t.slope, t.sss, t.pcc) if t.slope and t.sss else ''
            writer.writerow([t.name, t.date, total_score, total_sba, diff])
    return send_file(fp, as_attachment=True)


@app.route('/stats')
@login_required
def overall_stats():
    stats_entries = Stats.query.all()
    score_entries = Score.query.all()
    num_cards = len(stats_entries)
    total_putts = sum(s.putts_total for s in stats_entries)
    total_fairway_hits = sum(s.fairway_hits for s in stats_entries)
    total_fairway_possible = sum(s.fairway_possible for s in stats_entries)
    total_gir_hits = sum(s.gir_hits for s in stats_entries)
    total_scores = 0
    total_sba = 0
    diffs = []
    for s in score_entries:
        holes = s.holes or []
        card_score_total = sum(h.get('strokes', 0) for h in holes)
        total_scores += card_score_total
        card_sba_total = sum(h.get('adjusted') or 0 for h in holes)
        total_sba += card_sba_total
        t = db.session.get(Tour, s.tour_id)
        if t and t.slope and t.sss is not None:
            diffs.append(diff_whs(card_sba_total, t.slope, t.sss, t.pcc))
    avg_putts = format(total_putts / num_cards, '.1f') if num_cards else '0.0'
    avg_putts_cards = format(total_putts / (num_cards * 18), '.1f') if num_cards else '0.0'
    avg_score = format(total_scores / num_cards, '.1f') if num_cards else '0.0'
    avg_fairways = format(total_fairway_hits / num_cards, '.1f') if num_cards else '0.0'
    avg_sba = format(total_sba / num_cards, '.1f') if num_cards else '0.0'
    avg_nb_coups = format(total_scores / num_cards, '.1f') if num_cards else '0.0'
    fairway_pct = format(total_fairway_hits / total_fairway_possible * 100, '.1f') if total_fairway_possible else '0.0'
    gir_possible = num_cards * 18
    gir_pct = format(total_gir_hits / gir_possible * 100, '.1f') if gir_possible else '0.0'
    stats = {
        'avg_putts': avg_putts,
        'avg_putts_cards': avg_putts_cards,
        'avg_score': avg_score,
        'avg_fairways': avg_fairways,
        'fairway_pct': fairway_pct,
        'gir_pct': gir_pct,
        'avg_sba': avg_sba,
        'avg_nb_coups': avg_nb_coups,
        'diff_labels': list(range(1, len(diffs)+1)),
        'diff_values': diffs,
    }
    return render_template('stats_overall.html', stats=stats)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrate_from_tinydb()
    app.run(debug=True, host='0.0.0.0')
