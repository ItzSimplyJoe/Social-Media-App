function likePost(postId) {
    fetch(`/like_post/${postId}`, { method: 'POST' })
      .then((response) => response.json())
      .then((data) => {
        const likeCountSpan = document.getElementById(`likeCount${postId}`);
        likeCountSpan.textContent = data.likes_count;

        const heartIcon = document.getElementById(`heartIcon${postId}`);
        if (data.liked) {
          heartIcon.classList.add('liked'); 
          heartIcon.classList.remove('heartIcon');
        } else {
          heartIcon.classList.remove('liked');
          heartIcon.classList.add('heartIcon');
        }
      });
  }