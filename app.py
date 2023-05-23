from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    current_user,
    login_required,
)
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo
from sqlalchemy import text
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

# from app import db
from sqlalchemy.exc import SQLAlchemyError
import os
from werkzeug.utils import secure_filename
from flask_wtf.file import FileField, FileAllowed
from wtforms import PasswordField

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret_key_here"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class CreatePostForm(FlaskForm):
    content = TextAreaField("Contenido", validators=[DataRequired()])
    photo = FileField(
        "Foto",
        validators=[
            FileAllowed(ALLOWED_EXTENSIONS, "Solo se permiten archivos de imagen.")
        ],
    )


# Formulario de cambio de nombre de usuario
class ChangeUsernameForm(FlaskForm):
    username = StringField("Nuevo nombre de usuario", validators=[DataRequired()])


class UploadProfilePictureForm(FlaskForm):
    picture = FileField(
        "Foto de perfil",
        validators=[
            DataRequired(),
            FileAllowed(ALLOWED_EXTENSIONS, "Solo se permiten archivos de imagen."),
        ],
    )


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired()])
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Las contraseñas no coinciden."),
        ],
    )


likes = db.Table(
    "likes",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id"), primary_key=True),
)

# Modelo de relación de seguidores
followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("followed_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


# Modelo de usuario
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=False, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String(100))

    user_likes = db.relationship(
        "Post",
        secondary=likes,
        backref=db.backref("likes", lazy="dynamic"),
        lazy="dynamic",
    )

    # Relación para el seguimiento de usuarios
    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    # Método para seguir a un usuario
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    # Método para dejar de seguir a un usuario
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    # Método para verificar si se está siguiendo a un usuario
    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def __init__(self, username, password, profile_picture="hola"):
        self.username = username
        self.password = password
        self.profile_picture = profile_picture


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


# Modelo de Publicación
class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    photo = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("posts", lazy=True))

    likes_count = db.Column(db.Integer, default=0)
    post_likers = db.relationship(
        "User",
        secondary=likes,
        backref=db.backref("liked_posts", lazy="dynamic"),
        lazy="dynamic",
    )

    def like(self, user):
        if not self.is_liked_by(user):
            self.post_likers.append(user)
            self.likes_count += 1

    def unlike(self, user):
        if self.is_liked_by(user):
            self.post_likers.remove(user)
            self.likes_count -= 1

    def is_liked_by(self, user):
        return self.post_likers.filter(likes.c.user_id == user.id).count() > 0


class Comment(db.Model):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    text = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="comments")
    post = relationship("Post", backref="comments")


@app.route("/publicacion/<int:post_id>/agregar_comentario", methods=["POST"])
def agregar_comentario(post_id):
    comment_text = request.form["comment_text"]
    user = current_user  # Obtén el usuario actual de alguna manera (autenticación, sesión, etc.)
    post = Post.query.get(post_id)

    if comment_text:
        comment = Comment(text=comment_text, user=user, post=post)
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for("feed", post_id=post_id))


@app.route(
    "/publicacion/<int:post_id>/eliminar_comentario/<int:comment_id>", methods=["POST"]
)
def eliminar_comentario(post_id, comment_id):
    comment = Comment.query.get(comment_id)

    if comment:
        db.session.delete(comment)
        db.session.commit()

    return redirect(url_for("feed", post_id=post_id))


@app.route("/messages")
@login_required
def messages():
    # Obtener todos los usuarios excepto el usuario actual
    users = User.query.filter(User.id != current_user.id).all()
    return render_template("messages.html", users=users)


@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
def chat(user_id):
    user = User.query.get(user_id)
    if user is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("messages"))

    if request.method == "POST":
        content = request.form["content"]
        message = Message(sender=current_user, receiver=user, content=content)
        db.session.add(message)
        db.session.commit()
        flash("Mensaje enviado exitosamente.", "success")
        return redirect(url_for("chat", user_id=user_id))

    messages = (
        Message.query.filter(
            (Message.sender_id == current_user.id) & (Message.receiver_id == user_id)
            | (Message.sender_id == user_id) & (Message.receiver_id == current_user.id)
        )
        .order_by(Message.timestamp)
        .all()
    )

    return render_template("chat.html", user=user, messages=messages)


@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    post = Post.query.get(post_id)
    if post:
        post.like(current_user)
        db.session.commit()
    return redirect(url_for("feed"))


@app.route("/unlike/<int:post_id>", methods=["POST"])
@login_required
def unlike(post_id):
    post = Post.query.get(post_id)
    if post:
        post.unlike(current_user)
        db.session.commit()
    return redirect(url_for("feed"))


@app.route("/profile/<username>")
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("El usuario {} no existe.".format(username), "error")
        return redirect(url_for("feed"))

    return render_template("profile.html", user=user)


@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        content = form.content.data
        photo = form.photo.data

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        else:
            filename = None

        new_post = Post(content=content, photo=filename, user=current_user)
        db.session.add(new_post)
        db.session.commit()

        flash("La publicación se ha creado correctamente.")
        return redirect(url_for("feed"))

    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("create_post.html", form=form, posts=posts)


@app.route("/")
def feed():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("home.html", posts=posts)


@app.route("/follow/<int:user_id>", methods=["GET", "POST"])
@login_required
def follow(user_id):
    user = User.query.get(user_id)
    if user is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("index"))

    current_user.follow(user)
    db.session.commit()
    flash(f"Estás siguiendo a {user.username}.", "success")
    return redirect(url_for("profile", username=user.username))


@app.route("/unfollow/<int:user_id>", methods=["GET", "POST"])
@login_required
def unfollow(user_id):
    user = User.query.get(user_id)
    if user is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("index"))

    current_user.unfollow(user)
    db.session.commit()
    flash(f"Dejaste de seguir a {user.username}.", "success")
    return redirect(url_for("profile", username=user.username))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registro exitoso. Por favor, inicia sesión.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            return redirect(url_for("config"))

        flash("Nombre de usuario o contraseña incorrectos.")
        return redirect(url_for("login"))

    return render_template("login.html")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


UPLOAD_FOLDER = "static/profile_pictures"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/config", methods=["GET", "POST"])
@login_required
def config():
    form = UploadProfilePictureForm()
    formu = ChangeUsernameForm()
    formula = ChangePasswordForm()

    if form.validate_on_submit():
        file = form.picture.data

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            current_user.profile_picture = filename
            db.session.commit()

            flash("Foto de perfil actualizada exitosamente.")
            return redirect(url_for("config"))

    if formu.validate_on_submit():
        current_user.username = formu.username.data
        db.session.commit()
        flash("Nombre de usuario actualizado exitosamente.")
        return redirect(url_for("config"))

    if formula.validate_on_submit():
        current_password = formula.current_password.data
        new_password = formula.new_password.data

        # Verificar si la contraseña actual es correcta
        if current_user.password == current_password:
            current_user.password = new_password
            db.session.commit()

            flash("Contraseña actualizada exitosamente.")
            return redirect(url_for("feed"))
        else:
            flash("Contraseña actual incorrecta.", "error")

    return render_template("config.html", form=form, formu=formu, formula=formula)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "POST":
        search_query = request.form["search_query"]
        users = User.query.filter(User.username.ilike(f"%{search_query}%")).all()
        return render_template(
            "search_results.html", users=users, search_query=search_query
        )
    return render_template("home.html")


@app.route("/delete_post/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    try:
        # Eliminar los "likes" asociados al post
        db.session.execute(
            text("DELETE FROM likes WHERE post_id = :post_id"), {"post_id": post.id}
        )

        # Eliminar la publicación de la base de datos
        db.session.delete(post)
        db.session.commit()

        flash("La publicación ha sido eliminada correctamente.", "success")
        return redirect(url_for("feed"))

    except SQLAlchemyError:
        db.session.rollback()
        flash("No se pudo eliminar la publicación.", "error")
        return redirect(url_for("feed"))


@app.route("/delete_profile", methods=["POST"])
@login_required
def delete_profile():
    # Obtener el usuario actual
    user = current_user

    # Eliminar las publicaciones del usuario

    for post in current_user.posts:
        db.session.delete(post)
    db.session.commit()

    current_user.posts = []
    db.session.commit()

    # Eliminar el usuario de la base de datos
    db.session.delete(user)
    db.session.commit()

    flash("Tu perfil ha sido eliminado.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)