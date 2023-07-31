from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, Column, exists, or_, Table, ForeignKey, Integer, String, DateTime, Text, and_, alias
from sqlalchemy.orm import aliased, relationship
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_migrate import Migrate
import uuid
import os


app = Flask("Simplz")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

app.config['UPLOAD_FOLDER'] = 'static/users/uploaded_images'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

followers = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    extend_existing=True  # Add this option to reuse the existing table definition
)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.relationship('User', backref='comments', lazy=True)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    liked_at = db.Column(db.DateTime, default=datetime.utcnow)


class Follow(db.Model):
    __tablename__ = 'followers'
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

    follower = db.relationship('User', foreign_keys=[follower_id], backref='following')
    followed = db.relationship('User', foreign_keys=[followed_id], backref='followers')

    __table_args__ = {'extend_existing': True}

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Define the relationships with the User model
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50), default="Per")
    last_name = db.Column(db.String(50), default="Son")
    profession = db.Column(db.String(100), default="Person")
    location = db.Column(db.String(100), default="Earth")
    bio = db.Column(db.Text, default="Hello there...")
    profile_pic = db.Column(db.String(100), default='default.jpg')
    posts = db.relationship('Post', backref='author', lazy=True)

    following_list = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers_of', lazy='dynamic'),
        lazy='dynamic',
        overlaps="follower,followers_of,following,following_list"  # Add 'overlaps' parameter
    )

    followers_list = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        backref=db.backref('following_by', lazy='dynamic'),
        lazy='dynamic',
        overlaps="followed,followers,followers_of,following_list"  # Add 'overlaps' parameter
    )

    def is_following(self, user):
        return self.following_list.filter_by(id=user.id).first() is not None

    def follow(self, user):
        if not self.is_following(user) and self.id != user.id:
            self.following_list.append(user)
            db.session.commit()

    def unfollow(self, user):
        if self.is_following(user):
            self.following_list.remove(user)
            db.session.commit()

    def like_post(self, post):
        if not self.has_liked_post(post):
            like = Like(user_id=self.id, post_id=post.id)
            db.session.add(like)
            db.session.commit()

    def unlike_post(self, post):
        like = Like.query.filter_by(user_id=self.id, post_id=post.id).first()
        if like:
            db.session.delete(like)
            db.session.commit()

    def has_liked_post(self, post):
        return Like.query.filter_by(user_id=self.id, post_id=post.id).count() > 0

    def add_comment(self, post, content):
        comment = Comment(user_id=self.id, post_id=post.id, content=content)
        db.session.add(comment)
        db.session.commit()

    def delete_comment(self, comment):
        if comment.user_id == self.id:
            db.session.delete(comment)
            db.session.commit()



class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(100))
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True)
    @property
    def likes_count(self):
        return Like.query.filter_by(post_id=self.id).count()


login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
@login_required
def index():
    followed_user = aliased(User, name='followed_user')
    
    own_posts_query = Post.query.filter_by(user_id=current_user.id)
    
    followed_posts_query = Post.query.join(
        Follow,
        or_(
            and_(Post.user_id == Follow.followed_id, Follow.follower_id == current_user.id),
            and_(Post.user_id == Follow.follower_id, Follow.followed_id == current_user.id)
        )
    )

    combined_posts_query = own_posts_query.union_all(followed_posts_query)
    posts = combined_posts_query.order_by(Post.created_at.desc()).all()

    csrf_token = request.environ.get('HTTP_X_CSRFTOKEN')

    return render_template('index.html', posts=posts, csrf_token=csrf_token)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        password2 = request.form['password2']

        if password != password2:
            flash('Passwords do not match. Please try again.', 'error')
            return render_template('register.html')

        existing_user_with_username = User.query.filter_by(username=username).first()
        existing_user_with_email = User.query.filter_by(email=email).first()

        if existing_user_with_username:
            flash('Username already exists. Please choose a different username.', 'error')
            return render_template('register.html')

        if existing_user_with_email:
            flash('Email address already registered. Please use a different email.', 'error')
            return render_template('register.html')

        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Fields are case sensitive.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    content = request.form['content']
    image = request.files['image']

    if image and allowed_file(image.filename):
        filename = str(uuid.uuid4()) + secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        filename = None

    new_post = Post(content=content, author=current_user, filename=filename)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    if post and post.author == current_user:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('index'))



@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id, page):
    user_to_follow = User.query.get(user_id)
    if user_to_follow is None:
        flash('User not found.', 'error')
        return redirect(url_for('explore'))

    if current_user.is_following(user_to_follow):
        flash('You are already following this user.', 'info')
        return redirect(url_for('view_profile', user_id=user_id))

    try:
        current_user.follow(user_to_follow)
    except Exception as e:
        flash('Failed to follow the user. Please try again.', 'error')
        print(f"Error: {str(e)}")
        return redirect(url_for('view_profile', user_id=user_id))

    flash(f"You are now following {user_to_follow.username}.", 'success')
    if page == 'profile':
        return redirect(url_for('view_profile', user_id=user_id))
    elif page == 'search':
        return redirect(url_for('search_results', query=request.form['query']))
    else:
        return redirect(url_for('view_profile', user_id=user_id))


@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id, page):
    user_to_unfollow = User.query.get(user_id)
    if user_to_unfollow is None:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    if current_user.is_following(user_to_unfollow):
        current_user.unfollow(user_to_unfollow)
        flash('You have unfollowed {}.'.format(user_to_unfollow.username), 'success')
    else:
        flash('You are not following this user.', 'info')
    if page == 'profile':
        return redirect(url_for('view_profile', user_id=user_id))
    elif page == 'search':
        return redirect(url_for('search_results', query=request.form['query']))
    else:
        return redirect(url_for('view_profile', user_id=user_id))


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        current_user.username = request.form['username']
        current_user.email = request.form['email']
        current_user.first_name = request.form['first_name']
        current_user.last_name = request.form['last_name']
        current_user.bio = request.form['bio']
        current_user.location = request.form['location']
        current_user.profession = request.form['profession']

        profile_picture = request.files['profile_picture']
        if profile_picture and allowed_file(profile_picture.filename):
            filename = str(uuid.uuid4()) + secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            if current_user.profile_pic is not None and current_user.profile_pic != 'default.jpg':
                old_profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_pic)
                os.remove(old_profile_picture_path)

            current_user.profile_pic = filename

        new_password = request.form['new_password']
        if new_password:
            current_user.password = generate_password_hash(new_password, method='scrypt')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('account'))

    return render_template('account.html')

@app.route('/search_user', methods=['GET'])
def search_user():
    search_query = request.args.get('search_query', '')
    users = User.query.filter(User.username.ilike(f'%{search_query}%')).all()
    csrf_token = generate_csrf()  # Generate CSRF token
    return render_template('search_results.html', users=users, csrf_token=csrf_token)

@app.route('/user/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('search_user'))

    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    csrf_token = generate_csrf()  # Generate CSRF token
    return render_template('user_profile.html', user=user, posts=posts, csrf_token=csrf_token, profile_user_id=user_id)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form['content']

    # Find the post to which the comment is being added
    post = Post.query.get(post_id)
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('index'))

    # Create the comment and add it to the database
    current_user.add_comment(post, content)

    flash('Comment added successfully.', 'success')
    return redirect(url_for('index'))

@login_required
@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('index'))

    if current_user.has_liked_post(post):
        current_user.unlike_post(post)
        db.session.commit()
        liked = False
    else:
        current_user.like_post(post)
        db.session.commit()
        liked = True

    # Return JSON response with the updated likes count and liked status
    likes_count = post.likes_count
    response_data = {'likes_count': likes_count, 'liked': liked}
    return jsonify(response_data)


@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    recipient_username = request.form['recipient_username']
    message_content = request.form['message_content']

    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        flash('Recipient not found.', 'error')
        return redirect(url_for('conversations'))

    new_message = Message(sender_id=current_user.id, recipient_id=recipient.id, content=message_content)
    db.session.add(new_message)
    db.session.commit()

    flash('Message sent successfully!', 'success')
    return redirect(url_for('conversation', recipient_id=recipient.id))


@app.route('/conversations')
@login_required
def conversations():
    conversations = db.session.query(User).join(
        Message, or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == User.id),
            and_(Message.sender_id == User.id, Message.recipient_id == current_user.id)
        )
    ).distinct(User.id).all()

    return render_template('conversations.html', conversations=conversations)

@app.route('/new_conversation', methods=['GET'])
@login_required
def new_conversation():
    return render_template('new_conversation.html')



@app.route('/conversation/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def conversation(recipient_id):
    recipient = User.query.get(recipient_id)
    if not recipient:
        flash('Recipient not found.', 'error')
        return redirect(url_for('conversations'))

    if request.method == 'POST':
        message_content = request.form['message_content']

        new_message = Message(sender_id=current_user.id, recipient_id=recipient.id, content=message_content)
        db.session.add(new_message)
        db.session.commit()

        flash('Message sent successfully!', 'success')
        return redirect(url_for('conversation', recipient_id=recipient_id))

    messages = Message.query.filter(or_(
        and_(Message.sender_id == current_user.id, Message.recipient_id == recipient_id),
        and_(Message.sender_id == recipient_id, Message.recipient_id == current_user.id)
    )).order_by(Message.timestamp).all()

    return render_template('conversation.html', recipient=recipient, messages=messages)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, use_reloader=False)
