from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired
import os
from werkzeug.utils import secure_filename
from flask_wtf.file import FileField, FileAllowed
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
from datetime import datetime




app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class CreatePostForm(FlaskForm):
    content = TextAreaField('Contenido', validators=[DataRequired()])
    photo = FileField('Foto', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo se permiten archivos de imagen.')])

# Formulario de cambio de nombre de usuario
class ChangeUsernameForm(FlaskForm):
    username = StringField('Nuevo nombre de usuario', validators=[DataRequired()])

class UploadProfilePictureForm(FlaskForm):
    picture = FileField('Foto de perfil', validators=[DataRequired(), FileAllowed(ALLOWED_EXTENSIONS, 'Solo se permiten archivos de imagen.')])


# Modelo de Usuario
# class User(UserMixin, db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(100), unique=True)
#     password = db.Column(db.String(100))

#     def get_id(self):
#         return str(self.id)
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String(100))

    def __init__(self, username, password, profile_picture=None):
        self.username = username
        self.password = password
        self.profile_picture = profile_picture

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    photo = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))



# # Modelo de Publicación
# class Post(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     content = db.Column(db.Text)
#     user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
#     user = db.relationship('User', backref=db.backref('posts', lazy=True))


@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('El usuario {} no existe.'.format(username), 'error')
        return redirect(url_for('feed'))
    
    return render_template('profile.html', user=user)



@app.route('/create_post', methods=['GET','POST'])
@login_required
def create_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        content = form.content.data
        photo = form.photo.data

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None

        new_post = Post(content=content, photo=filename, user=current_user)
        db.session.add(new_post)
        db.session.commit()

        flash('La publicación se ha creado correctamente.')
        return redirect(url_for('feed'))

    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('create_post.html', form=form, posts=posts)



@app.route('/')
def feed():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('home.html', posts=posts)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('El usuario {} no existe.'.format(username), 'error')
        return redirect(url_for('home'))

    if user == current_user:
        flash('No puedes seguirte a ti mismo.', 'error')
        return redirect(url_for('profile', username=username))

    current_user.follow(user)
    db.session.commit()
    flash('Ahora sigues a {}.'.format(username), 'success')
    return redirect(url_for('profile', username=username))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registro exitoso. Por favor, inicia sesión.')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('feed'))
        
        flash('Nombre de usuario o contraseña incorrectos.')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/change_username', methods=['GET', 'POST'])
@login_required
def change_username():
    form = ChangeUsernameForm()
    
    if form.validate_on_submit():
        current_user.username = form.username.data
        db.session.commit()
        flash('Nombre de usuario actualizado exitosamente.')
        return redirect(url_for('feed'))
    
    return render_template('change_username.html', form=form)


# @app.route('/create_post', methods=['POST'])
# @login_required
# def create_post():
#     content = request.form['content']
    
#     new_post = Post(content=content, user=current_user)
#     db.session.add(new_post)
#     db.session.commit()
    
#     flash('Publicación creada exitosamente.')
#     return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



UPLOAD_FOLDER = 'static/profile_pictures'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_profile_picture', methods=['GET', 'POST'])
@login_required
def upload_profile_picture():
    form = UploadProfilePictureForm()

    if form.validate_on_submit():
        file = form.picture.data

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            current_user.profile_picture = filename
            db.session.commit()
            
            flash('Foto de perfil actualizada exitosamente.')
            return redirect(url_for('feed'))

    return render_template('upload_profile_picture.html', form=form)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)

    # Verificar si la publicación existe
    if post is None:
        flash('La publicación no existe.', 'error')
        return redirect(url_for('home'))

    # Verificar si el usuario actual es el propietario de la publicación
    if post.user != current_user:
        flash('No tienes permiso para eliminar esta publicación.', 'error')
        return redirect(url_for('feed'))

    # Eliminar la publicación de la base de datos
    db.session.delete(post)
    db.session.commit()

    flash('La publicación ha sido eliminada.', 'success')
    return redirect(url_for('feed'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
