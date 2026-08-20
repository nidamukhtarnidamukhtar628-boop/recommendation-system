from dotenv import load_dotenv
import os

load_dotenv()
from flask import Flask, render_template, request, redirect, jsonify
import pickle
import pandas as pd
import requests
from models import db, User, Favorite
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)

# ============================================
# Database Configuration
# ============================================
mysql_password = os.getenv('MYSQL_PASSWORD')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://root:{mysql_password}@localhost/smartrec_db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db.init_app(app)

with app.app_context():
    db.create_all()


# ============================================
# Login Manager Setup
# ============================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================
# Load ML Model Files
# ============================================
tfidf = pickle.load(open('model/tfidf.pkl', 'rb'))
similarity = pickle.load(open('model/similarity.pkl', 'rb'))
movies = pd.read_pickle('model/movies.pkl')
movies = movies.reset_index(drop=True)

TMDB_API_KEY = os.getenv('TMDB_API_KEY')


# ============================================
# Helper Functions
# ============================================
def get_poster_url(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
        response = requests.get(url)
        data = response.json()
        poster_path = data.get('poster_path')
        if poster_path:
            return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception:
        pass
    return "https://placehold.co/300x450/1a1a2e/white?text=No+Poster"


def get_similar_movies(idx, top_n=6):
    sim_scores = list(enumerate(similarity[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = [s for s in sim_scores if s[0] != idx][:top_n]

    similar = []
    for i, score in sim_scores:
        row = movies.iloc[i]
        similar.append({
            'id': row['id'],
            'title': row['title'],
            'poster': get_poster_url(row['id']),
            'rating': row['vote_average']
        })
    return similar


def get_favorite_ids():
    if current_user.is_authenticated:
        favs = Favorite.query.filter_by(user_id=current_user.id).all()
        return {f.movie_id for f in favs}
    return set()


# ============================================
# Routes
# ============================================
@app.route('/')
def home():
    top_movies = movies[movies['vote_average'] > 0].sort_values('vote_average', ascending=False).head(12)

    featured = []
    for _, row in top_movies.iterrows():
        featured.append({
            'id': row['id'],
            'title': row['title'],
            'genres': row['genres_clean'],
            'rating': row['vote_average'],
            'poster': get_poster_url(row['id'])
        })

    return render_template('index.html', movies=featured, favorite_ids=get_favorite_ids())


@app.route('/search')
def search():
    query = request.args.get('query', '').strip()

    if not query:
        return render_template('search.html', query=query, results=[], favorite_ids=get_favorite_ids())

    matches = movies[movies['title'].str.contains(query, case=False, na=False)].head(5)

    results = []
    for idx, row in matches.iterrows():
        results.append({
            'id': row['id'],
            'title': row['title'],
            'genres': row['genres_clean'],
            'overview': row['overview'],
            'rating': row['vote_average'],
            'poster': get_poster_url(row['id']),
            'similar': get_similar_movies(idx)
        })

    return render_template('search.html', query=query, results=results, favorite_ids=get_favorite_ids())


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    row = movies[movies['id'] == movie_id]

    if row.empty:
        return "Movie nahi mili", 404

    row = row.iloc[0]
    idx = row.name

    movie = {
        'id': row['id'],
        'title': row['title'],
        'genres': row['genres_clean'],
        'overview': row['overview'],
        'rating': row['vote_average'],
        'release_date': row['release_date'],
        'poster': get_poster_url(row['id']),
        'similar': get_similar_movies(idx)
    }

    return render_template('movie_detail.html', movie=movie, favorite_ids=get_favorite_ids())


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Ye email pehle se registered hai.")

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect('/')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect('/')
        else:
            return render_template('login.html', error="Email ya password galat hai.")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/favorite/<int:movie_id>', methods=['POST'])
@login_required
def toggle_favorite(movie_id):
    movie_title = request.form.get('movie_title')

    existing = Favorite.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()

    if existing:
        db.session.delete(existing)
        is_favorited = False
    else:
        new_fav = Favorite(user_id=current_user.id, movie_id=movie_id, movie_title=movie_title)
        db.session.add(new_fav)
        is_favorited = True

    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'favorited': is_favorited})

    return redirect(request.referrer or '/')


@app.route('/favorites')
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()

    fav_movies = []
    for f in favs:
        fav_movies.append({
            'id': f.movie_id,
            'title': f.movie_title,
            'poster': get_poster_url(f.movie_id)
        })

    return render_template('favorites.html', movies=fav_movies)


if __name__ == '__main__':
    app.run(debug=True)