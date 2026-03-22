import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin,
)
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# =========================
# CONFIG
# =========================
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["BOOK_UPLOAD_FOLDER"] = os.path.join("static", "images", "books")
app.config["NOTES_UPLOAD_FOLDER"] = os.path.join("static", "uploads", "notes")
app.config["PROFILE_UPLOAD_FOLDER"] = os.path.join("static", "images", "profiles")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

os.makedirs(app.config["BOOK_UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["NOTES_UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PROFILE_UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_NOTE_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx"}

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# =========================
# GOOGLE OAUTH
# =========================
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# =========================
# HELPERS
# =========================
def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def profile_image_url(profile_pic):
    if not profile_pic:
        return url_for("static", filename="images/default-user.png")

    if profile_pic.startswith("http://") or profile_pic.startswith("https://"):
        return profile_pic

    return url_for("static", filename=f"images/profiles/{profile_pic}")


app.jinja_env.globals.update(profile_image_url=profile_image_url)

# =========================
# DATABASE MODELS
# =========================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    profile_pic = db.Column(db.String(500), nullable=True)

    books = db.relationship("Book", backref="owner", lazy=True, cascade="all, delete-orphan")
    notes = db.relationship("Note", backref="uploader", lazy=True, cascade="all, delete-orphan")
    cart_items = db.relationship("Cart", backref="cart_user", lazy=True, cascade="all, delete-orphan")


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_name = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(300), nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    condition = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    cart_items = db.relationship("Cart", backref="cart_book", lazy=True, cascade="all, delete-orphan")


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =========================
# TEMPLATE FILTER
# =========================
@app.template_filter("book_image_url")
def book_image_url(image_name):
    if image_name:
        return url_for("static", filename=f"images/books/{image_name}")
    return url_for("static", filename="images/placeholder_book.png")


# =========================
# HOME
# =========================
@app.route("/")
def index():
    books = Book.query.order_by(Book.id.desc()).limit(8).all()
    return render_template("index.html", books=books)


@app.route("/home")
def home():
    q = request.args.get("q", "").strip()

    if q:
        books = Book.query.filter(
            (Book.book_name.ilike(f"%{q}%")) |
            (Book.author.ilike(f"%{q}%"))
        ).order_by(Book.id.desc()).all()
    else:
        books = Book.query.order_by(Book.id.desc()).all()

    return render_template("home.html", books=books)


# =========================
# AUTH
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            flash("Please fill all required fields.")
            return redirect(url_for("signup"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.")
            return redirect(url_for("signup"))

        user = User(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        flash("Signup successful. Please login.")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please enter email and password.")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful.")
            return redirect(url_for("home"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.")
    return redirect(url_for("index"))


# =========================
# GOOGLE LOGIN
# =========================
@app.route("/google-login")
def google_login():
    return google.authorize_redirect(url_for("google_callback", _external=True))


@app.route("/google-callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        try:
            user_info = google.get("userinfo").json()
        except Exception:
            user_info = None

    if not user_info:
        flash("Google login failed.")
        return redirect(url_for("login"))

    email = user_info.get("email")
    name = user_info.get("name", "Google User")
    picture = user_info.get("picture")

    if not email:
        flash("Google login failed: email not received.")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            password=generate_password_hash("google_login"),
            profile_pic=picture,
        )
        db.session.add(user)
    else:
        if name and not user.name:
            user.name = name
        if picture and (not user.profile_pic or user.profile_pic.startswith("http")):
            user.profile_pic = picture

    db.session.commit()
    login_user(user)
    flash("Logged in with Google successfully.")
    return redirect(url_for("profile"))


# =========================
# PROFILE
# =========================
@app.route("/profile")
@login_required
def profile():
    my_books = Book.query.filter_by(user_id=current_user.id).order_by(Book.id.desc()).all()
    my_notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.id.desc()).all()
    return render_template("profile.html", my_books=my_books, my_notes=my_notes)


@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    image_file = request.files.get("profile_pic")

    if not name:
        flash("Name cannot be empty.")
        return redirect(url_for("profile"))

    current_user.name = name
    current_user.phone = phone

    if image_file and image_file.filename:
        if not allowed_file(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            flash("Only png, jpg, jpeg, webp images are allowed.")
            return redirect(url_for("profile"))

        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["PROFILE_UPLOAD_FOLDER"], filename)
        image_file.save(image_path)
        current_user.profile_pic = filename

    db.session.commit()
    flash("Profile updated successfully.")
    return redirect(url_for("profile"))


# =========================
# BOOKS
# =========================
@app.route("/book/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)


@app.route("/sell-book", methods=["GET", "POST"])
@login_required
def sell_book():
    if request.method == "POST":
        book_name = request.form.get("book_name", "").strip()
        author = request.form.get("author", "").strip()
        price = request.form.get("price", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        condition = request.form.get("condition", "").strip()
        description = request.form.get("description", "").strip()
        image_file = request.files.get("image")

        if not book_name or not author or not price:
            flash("Please fill all required fields.")
            return redirect(url_for("sell_book"))

        try:
            price_value = float(price)
        except ValueError:
            flash("Please enter a valid price.")
            return redirect(url_for("sell_book"))

        filename = None
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("Only png, jpg, jpeg, webp images are allowed.")
                return redirect(url_for("sell_book"))

            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["BOOK_UPLOAD_FOLDER"], filename)
            image_file.save(image_path)

        book = Book(
            book_name=book_name,
            author=author,
            price=price_value,
            image=filename,
            contact_number=contact_number,
            condition=condition,
            description=description,
            user_id=current_user.id,
        )
        db.session.add(book)
        db.session.commit()

        flash("Book uploaded successfully.")
        return redirect(url_for("home"))

    return render_template("sell_book.html")


@app.route("/edit-book/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if book.user_id != current_user.id:
        flash("You are not allowed to edit this book.")
        return redirect(url_for("home"))

    if request.method == "POST":
        book_name = request.form.get("book_name", "").strip()
        author = request.form.get("author", "").strip()
        price = request.form.get("price", "").strip()

        if not book_name or not author or not price:
            flash("Please fill all required fields.")
            return redirect(url_for("edit_book", book_id=book.id))

        try:
            price_value = float(price)
        except ValueError:
            flash("Please enter a valid price.")
            return redirect(url_for("edit_book", book_id=book.id))

        book.book_name = book_name
        book.author = author
        book.price = price_value
        book.contact_number = request.form.get("contact_number", "").strip()
        book.condition = request.form.get("condition", "").strip()
        book.description = request.form.get("description", "").strip()

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("Only png, jpg, jpeg, webp images are allowed.")
                return redirect(url_for("edit_book", book_id=book.id))

            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["BOOK_UPLOAD_FOLDER"], filename)
            image_file.save(image_path)
            book.image = filename

        db.session.commit()
        flash("Book updated successfully.")
        return redirect(url_for("book_detail", book_id=book.id))

    return render_template("edit_book.html", book=book)


@app.route("/delete-book/<int:book_id>")
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    if book.user_id != current_user.id:
        flash("You are not allowed to delete this book.")
        return redirect(url_for("home"))

    db.session.delete(book)
    db.session.commit()
    flash("Book deleted successfully.")
    return redirect(url_for("profile"))


# =========================
# NOTES
# =========================
@app.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        note_file = request.files.get("file")

        if not title or not note_file or not note_file.filename:
            flash("Please provide title and file.")
            return redirect(url_for("notes"))

        if not allowed_file(note_file.filename, ALLOWED_NOTE_EXTENSIONS):
            flash("Only pdf, doc, docx, ppt, pptx files are allowed.")
            return redirect(url_for("notes"))

        filename = secure_filename(note_file.filename)
        file_path = os.path.join(app.config["NOTES_UPLOAD_FOLDER"], filename)
        note_file.save(file_path)

        note = Note(
            title=title,
            description=description,
            file=filename,
            user_id=current_user.id,
        )
        db.session.add(note)
        db.session.commit()

        flash("Notes uploaded successfully.")
        return redirect(url_for("notes"))

    all_notes = Note.query.order_by(Note.id.desc()).all()
    return render_template("notes.html", notes=all_notes)


@app.route("/edit-note/<int:note_id>", methods=["GET", "POST"])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.user_id != current_user.id:
        flash("You are not allowed to edit this note.")
        return redirect(url_for("notes"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        note_file = request.files.get("file")

        if not title:
            flash("Title is required.")
            return redirect(url_for("edit_note", note_id=note.id))

        note.title = title
        note.description = description

        if note_file and note_file.filename:
            if not allowed_file(note_file.filename, ALLOWED_NOTE_EXTENSIONS):
                flash("Only pdf, doc, docx, ppt, pptx files are allowed.")
                return redirect(url_for("edit_note", note_id=note.id))

            filename = secure_filename(note_file.filename)
            file_path = os.path.join(app.config["NOTES_UPLOAD_FOLDER"], filename)
            note_file.save(file_path)
            note.file = filename

        db.session.commit()
        flash("Note updated successfully.")
        return redirect(url_for("profile"))

    return render_template("edit_note.html", note=note)


@app.route("/delete-note/<int:note_id>")
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.user_id != current_user.id:
        flash("You are not allowed to delete this note.")
        return redirect(url_for("notes"))

    db.session.delete(note)
    db.session.commit()
    flash("Note deleted successfully.")
    return redirect(url_for("profile"))


@app.route("/download-note/<filename>")
@login_required
def download_note(filename):
    return send_from_directory(app.config["NOTES_UPLOAD_FOLDER"], filename, as_attachment=True)


# =========================
# CART
# =========================
@app.route("/add-to-cart/<int:book_id>")
@login_required
def add_to_cart(book_id):
    book = Book.query.get_or_404(book_id)

    existing = Cart.query.filter_by(user_id=current_user.id, book_id=book.id).first()
    if existing:
        flash("Book already in cart.")
        return redirect(url_for("cart"))

    cart_item = Cart(user_id=current_user.id, book_id=book.id)
    db.session.add(cart_item)
    db.session.commit()

    flash("Book added to cart.")
    return redirect(url_for("cart"))


@app.route("/cart")
@login_required
def cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    books = [item.cart_book for item in cart_items if item.cart_book]
    return render_template("cart.html", books=books)


@app.route("/remove-from-cart/<int:book_id>")
@login_required
def remove_from_cart(book_id):
    cart_item = Cart.query.filter_by(user_id=current_user.id, book_id=book_id).first()

    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash("Removed from cart.")
    else:
        flash("Book not found in cart.")

    return redirect(url_for("cart"))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)